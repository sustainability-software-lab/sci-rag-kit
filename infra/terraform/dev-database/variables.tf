variable "project_id" {
  description = "Google Cloud project that owns the shared development database."
  type        = string
  default     = "pisces-476117"
}

variable "region" {
  description = "Cloud SQL region. Choose one near the developers using the proxy."
  type        = string
  default     = "us-west1"
}

variable "instance_name" {
  description = "Name of the shared development-only Cloud SQL instance."
  type        = string
  default     = "sci-rag-dev"
}

variable "db_tier" {
  description = "Smallest sensible development tier; increase only after measurement."
  type        = string
  default     = "db-g1-small"
}

variable "database_user" {
  description = "Built-in PostgreSQL user shared by workspace databases."
  type        = string
  default     = "sci_rag"
}

variable "developer_principal" {
  description = "IAM principal that runs the helper, for example user:name@example.org."
  type        = string
}

variable "deletion_protection" {
  description = "Protect the disposable dev instance from terraform destroy."
  type        = bool
  default     = false
}
