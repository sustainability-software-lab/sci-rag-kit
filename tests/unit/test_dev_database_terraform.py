"""Static security and isolation contract for the dev-only Cloud SQL module."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
MODULE = REPO_ROOT / "infra" / "terraform" / "dev-database"


def _terraform_text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(MODULE.glob("*.tf")))


def test_dev_module_is_separate_and_defaults_to_the_approved_project() -> None:
    assert (MODULE / "main.tf").exists()
    assert (MODULE / "variables.tf").exists()
    assert (MODULE / "outputs.tf").exists()
    text = _terraform_text()

    assert 'default     = "pisces-476117"' in text
    assert 'default     = "us-west1"' in text
    assert 'default     = "sci-rag-dev"' in text
    assert 'default     = "db-g1-small"' in text
    assert 'edition           = "ENTERPRISE"' in text
    assert "deletion_protection = var.deletion_protection" in text
    assert "default     = false" in text
    assert "ignore_changes = [settings[0].activation_policy]" in text


def test_dev_instance_uses_proxy_only_public_connectivity() -> None:
    text = _terraform_text()

    assert "ipv4_enabled = true" in text
    assert "authorized_networks" not in text
    assert 'database_version = "POSTGRES_16"' in text


def test_developer_access_is_limited_to_the_dev_instance_and_secret() -> None:
    text = _terraform_text()

    assert 'role    = "roles/cloudsql.editor"' in text
    assert "resource.name.startsWith" in text
    assert 'role      = "roles/secretmanager.secretAccessor"' in text
    assert "google_secret_manager_secret.password.id" in text


def test_module_outputs_the_helper_configuration_without_the_password() -> None:
    outputs = (MODULE / "outputs.tf").read_text(encoding="utf-8")

    assert 'output "connection_name"' in outputs
    assert 'output "instance_name"' in outputs
    assert 'output "sci_rag_cloud_pg_config"' in outputs
    assert "SCI_RAG_CLOUD_PG_PROJECT" in outputs
    assert "SCI_RAG_CLOUD_PG_INSTANCE" in outputs
    assert "SCI_RAG_CLOUD_PG_REGION" in outputs
    assert "random_password" not in outputs
