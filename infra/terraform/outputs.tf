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

output "run_ingest_example" {
  description = "Example: execute the ops job with an ingest command instead of migrations."
  value       = "gcloud run jobs execute ${google_cloud_run_v2_job.ops.name} --region=${var.region} --project=${var.project_id} --args='ingest,--manifest,data/demo/manifest.jsonl' --wait"
}
