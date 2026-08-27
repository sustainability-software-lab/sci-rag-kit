# Minimal, honest Google Cloud deployment for a sci-rag instance:
# Cloud SQL (Postgres + pgvector), a Cloud Run service for the API/MCP,
# a Cloud Run job for migrations and ingestion, and a corpus bucket.
#
# Costs money while it exists (the database is the steady cost; pick the
# smallest tier that fits). Tear down with `terraform destroy`.

terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.30"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.5"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# --- Database ---------------------------------------------------------------

resource "google_sql_database_instance" "db" {
  name             = "${var.name}-db"
  database_version = "POSTGRES_16"
  region           = var.region

  settings {
    tier = var.db_tier
    ip_configuration {
      ipv4_enabled = true # access is via the Cloud SQL connector, not open TCP
    }
    backup_configuration {
      enabled = true
    }
  }

  deletion_protection = var.deletion_protection
}

resource "google_sql_database" "sci_rag" {
  name     = "sci_rag"
  instance = google_sql_database_instance.db.name
}

resource "random_password" "db" {
  length  = 24
  special = false
}

resource "google_sql_user" "sci_rag" {
  name     = "sci_rag"
  instance = google_sql_database_instance.db.name
  password = random_password.db.result
}

# The async driver reaches Cloud SQL over the mounted unix socket.
locals {
  database_url = "postgresql+asyncpg://sci_rag:${random_password.db.result}@/sci_rag?host=/cloudsql/${google_sql_database_instance.db.connection_name}"
}

# --- Secrets ----------------------------------------------------------------

resource "google_secret_manager_secret" "database_url" {
  secret_id = "${var.name}-database-url"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "database_url" {
  secret      = google_secret_manager_secret.database_url.id
  secret_data = local.database_url
}

resource "google_secret_manager_secret" "api_keys" {
  secret_id = "${var.name}-api-keys"
  replication {
    auto {}
  }
}

# Seed with an empty JSON object; set real keys with:
#   echo '{"my-key": {"scopes": ["retrieval:query"]}}' | \
#     gcloud secrets versions add <name>-api-keys --data-file=-
resource "google_secret_manager_secret_version" "api_keys_seed" {
  secret      = google_secret_manager_secret.api_keys.id
  secret_data = "{}"
  lifecycle {
    ignore_changes = [secret_data]
  }
}

# --- Service account (least privilege) --------------------------------------

resource "google_service_account" "runtime" {
  account_id   = "${var.name}-runtime"
  display_name = "sci-rag runtime"
}

resource "google_project_iam_member" "cloudsql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "vertex" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_secret_manager_secret_iam_member" "db_url_access" {
  secret_id = google_secret_manager_secret.database_url.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_secret_manager_secret_iam_member" "api_keys_access" {
  secret_id = google_secret_manager_secret.api_keys.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

# --- Corpus bucket ----------------------------------------------------------

resource "google_storage_bucket" "corpus" {
  name                        = "${var.project_id}-${var.name}-corpus"
  location                    = var.region
  uniform_bucket_level_access = true
  versioning {
    enabled = true
  }
}

resource "google_storage_bucket_iam_member" "corpus_access" {
  bucket = google_storage_bucket.corpus.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.runtime.email}"
}

# --- Cloud Run service (REST + MCP) -----------------------------------------

resource "google_cloud_run_v2_service" "api" {
  name     = var.name
  location = var.region

  template {
    service_account = google_service_account.runtime.email

    containers {
      image = var.image

      env {
        name = "SCI_RAG_DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database_url.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "SCI_RAG_API_KEYS"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.api_keys.secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "SCI_RAG_GCP_PROJECT"
        value = var.project_id
      }
      env {
        name  = "SCI_RAG_GCP_LOCATION"
        value = var.region
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }

      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 5
        period_seconds        = 5
        failure_threshold     = 6
      }
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.db.connection_name]
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = var.max_instances
    }
  }

  depends_on = [google_secret_manager_secret_version.database_url]
}

# Public or not is your call; default is authenticated-only at the
# Google layer, with the app's API keys as the second layer.
resource "google_cloud_run_v2_service_iam_member" "public" {
  count    = var.allow_unauthenticated ? 1 : 0
  name     = google_cloud_run_v2_service.api.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# --- Cloud Run job (migrations and ingestion, same image) -------------------

resource "google_cloud_run_v2_job" "ops" {
  name     = "${var.name}-ops"
  location = var.region

  template {
    template {
      service_account = google_service_account.runtime.email
      max_retries     = 0

      containers {
        image   = var.image
        command = ["sci-rag"]
        args    = ["db", "upgrade"] # override per execution, see outputs

        env {
          name = "SCI_RAG_DATABASE_URL"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.database_url.secret_id
              version = "latest"
            }
          }
        }
        env {
          name  = "SCI_RAG_GCP_PROJECT"
          value = var.project_id
        }
        env {
          name  = "SCI_RAG_GCP_LOCATION"
          value = var.region
        }

        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
      }

      volumes {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [google_sql_database_instance.db.connection_name]
        }
      }
    }
  }
}
