output "service_url" {
  description = "The Cloud Run URL (docs at /docs, MCP at /mcp)."
  value       = google_cloud_run_v2_service.api.uri
}

output "db_connection_name" {
  description = "Cloud SQL connection name (for the Auth Proxy during ingestion from your laptop)."
  value       = google_sql_database_instance.db.connection_name
}

output "corpus_bucket" {
  value = google_storage_bucket.corpus.name
}

output "run_migrations" {
  description = "Run this once after every deploy that changes the schema."
  value       = "gcloud run jobs execute ${google_cloud_run_v2_job.ops.name} --region=${var.region} --project=${var.project_id} --wait"
}

# An example that runs. The previous one passed `data/demo/manifest.jsonl`,
# which no image contains: `.gcloudignore` and `.dockerignore` both exclude
# `data/` so a private corpus cannot be uploaded into an image, and that
# exclusion is load-bearing rather than an oversight. `doctor` needs no corpus,
# so it demonstrates the same thing the example was for, which is running the
# ops job with a command other than migrations.
output "run_ops_job_example" {
  description = "Example: execute the ops job with a command other than migrations."
  value       = "gcloud run jobs execute ${google_cloud_run_v2_job.ops.name} --region=${var.region} --project=${var.project_id} --args='doctor' --wait"
}

# Where a corpus goes, and why ingesting one is not a one-liner. `load_manifest`
# reads a local path, so a manifest in this bucket is not directly ingestible:
# the corpus has to reach the container's filesystem first, by baking it into
# the image or fetching it at start. Saying so here beats leaving an operator
# to find out from a FileNotFoundError.
output "corpus_bucket_purpose" {
  description = "What the corpus bucket is for, and the constraint on using it."
  value       = "Stage corpora in gs://${google_storage_bucket.corpus.name}. The runtime service account can read it, but `sci-rag ingest --manifest` takes a local path, so fetch into the container before ingesting."
}

# Where to read the generated first API key. Deliberately not the key itself:
# a Terraform output lands in state, and state is already a credential we tell
# operators not to circulate. This prints the command instead.
output "read_first_api_key" {
  description = "How to read the API key the deploy generated."
  value       = "gcloud secrets versions access latest --secret=${google_secret_manager_secret.api_keys.secret_id} --project=${var.project_id}"
}
