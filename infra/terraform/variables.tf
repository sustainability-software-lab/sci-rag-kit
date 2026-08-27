variable "project_id" {
  description = "Google Cloud project id."
  type        = string
}

variable "region" {
  description = "Region for everything (Cloud SQL, Cloud Run, bucket)."
  type        = string
  default     = "us-central1"
}

variable "name" {
  description = "Base name for resources (service, db, secrets)."
  type        = string
  default     = "sci-rag"
}

variable "image" {
  description = "Container image (for example REGION-docker.pkg.dev/PROJECT/REPO/sci-rag:TAG). Build it from the repo Dockerfile."
  type        = string
}

variable "db_tier" {
  description = "Cloud SQL machine tier. db-g1-small is the smallest sensible dev tier; size up for real load."
  type        = string
  default     = "db-g1-small"
}

variable "max_instances" {
  description = "Cloud Run max instances."
  type        = number
  default     = 3
}

variable "allow_unauthenticated" {
  description = "Expose the service publicly at the Google layer (the app's own API keys still apply)."
  type        = bool
  default     = false
}

variable "deletion_protection" {
  description = "Protect the database from accidental terraform destroy."
  type        = bool
  default     = true
}
