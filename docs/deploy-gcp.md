---
title: Deploy on Google Cloud
description: Provision Cloud SQL and Cloud Run from the included Terraform, then verify infrastructure and schema readiness.
---

# Deploy on Google Cloud

Provision a Cloud Run service backed by Cloud SQL with pgvector, then verify service health and
database migrations. The shipped container image does not include corpus data, so this guide stops
at infrastructure and database readiness.

<div class="srag-meta-strip">
  <div><strong>You'll build</strong>One Cloud Run service and one Cloud SQL instance</div>
  <div><strong>You'll need</strong>A Google Cloud project and billing enabled</div>
  <div><strong>Time</strong>Depends on provisioning and organization policy</div>
  <div><strong>Cost</strong>Varies by region and selected resource tiers; charges continue until teardown</div>
  <div><strong>Tested with</strong>v0.4</div>
</div>

!!! note "Terraform is optional"

    Generated projects include the production Terraform module by default. To
    change that choice, run `sci-rag new --advanced` for a new project or
    `sci-rag init --advanced` in an existing checkout. Choosing `No` for
    `include_terraform` removes `infra/terraform/` and its CI job. You can
    restore both from
    [the template](https://github.com/sustainability-software-lab/sci-rag-kit/tree/main/infra/terraform)
    later.

The kit ships Terraform under `infra/terraform/` for Cloud SQL with pgvector, one
Cloud Run service for REST and MCP, an operations job, a corpus bucket, secrets, and a
least-privilege service account.

<!-- BEGIN GENERATED PROJECT FEATURE: cloud-provisioning -->
!!! warning "The development database is a different module"

    `infra/terraform/dev-database/` provisions a shared, pausable development
    instance for laptop access through the Cloud SQL Auth Proxy. The
    `scripts/cloud_postgres.py` creates workspace-scoped databases dynamically.
    The development module disables backups and deletion
    protection by default. Never point a deployment at it. This page uses the production-shaped path.
<!-- END GENERATED PROJECT FEATURE: cloud-provisioning -->

These resources accrue charges while they run. Review the selected tiers and region in the saved
Terraform plan, and tear down experiments with `terraform destroy`.

## Before you start

* A Google Cloud project with billing enabled and `gcloud` authenticated
  (`gcloud auth login` plus `gcloud auth application-default login`).
* APIs enabled once per project:

```bash
gcloud services enable run.googleapis.com sqladmin.googleapis.com \
  secretmanager.googleapis.com artifactregistry.googleapis.com \
  aiplatform.googleapis.com cloudbuild.googleapis.com \
  iam.googleapis.com --project=YOUR_PROJECT
```

* Terraform 1.5+.

## Step 1: build and push the image

```bash
gcloud artifacts repositories create sci-rag --repository-format=docker \
  --location=us-central1 --project=YOUR_PROJECT   # once

gcloud builds submit --project=YOUR_PROJECT \
  --tag us-central1-docker.pkg.dev/YOUR_PROJECT/sci-rag/sci-rag:v1 .
```

The Dockerfile packages the kit, the `domain/` folder, and migrations. The same image
serves the API and runs schema upgrades. Rebuild whenever the domain changes.

!!! warning "The trailing dot uploads the directory"

    `gcloud builds submit ... .` sends the current directory to Cloud Build. `.gcloudignore` and `.dockerignore` control what is sent. Both allow only: `pyproject.toml`, `uv.lock`, `README.md`, `alembic.ini`, `src/`, `domain/`, `migrations/`, and `Dockerfile`.

    Credentials, `.env` files, Terraform state, and restricted papers stay safe by default. The corpus in `data/raw/` is excluded. If you add a `COPY` to the Dockerfile, add its source to both manifests. `tests/unit/test_build_context.py` enforces this.

    Do not delete `.gcloudignore` to upload everything. Without it, gcloud falls back to `.gitignore`, which misses entries in `.git/info/exclude`.

## Step 2: terraform apply

```bash
cd infra/terraform
terraform init
terraform apply \
  -var project_id=YOUR_PROJECT \
  -var image=us-central1-docker.pkg.dev/YOUR_PROJECT/sci-rag/sci-rag:v1
```

What you get:

* The database is reachable only through the Cloud SQL connector (mounted as a Unix socket), never via open TCP.
* The runtime service account holds `cloudsql.client`, `aiplatform.user`, and read access to two secrets.
* Send API keys as `X-API-Key: <key>`. Cloud Run's frontend claims `Authorization: Bearer` for its own identity tokens, so use the alternate header.
* The Cloud Run service is private by default. Pass `-var allow_unauthenticated=true` to make API keys the only gate.

## Step 3: migrate the database

```bash
# Create the schema. Terraform output prints this exact command.
gcloud run jobs execute sci-rag-ops --region=us-central1 --project=YOUR_PROJECT --wait
```

The current image deliberately excludes `data/`, including the demo manifest and any
private corpus. It therefore does not yet provide an image-baked ingestion path. Issue
[#189](https://github.com/sustainability-software-lab/sci-rag-kit/issues/189) tracks the
corpus-delivery and teardown qualification. Do not add corpus files to the image or
remove the ignore rules as a workaround; that can publish restricted documents in an
image layer.

Until a delivery path is qualified, this guide proves infrastructure and schema setup.
The deployed corpus remains incomplete. Keep ingestion on a separately reviewed path
that does not expose source documents, and do not call the deployment complete from
the checks below.

## Step 4: set API keys and verify

```bash
echo '{"team-key": {"scopes": ["retrieval:query", "retrieval:answer", "corpus:read"]}}' | \
  gcloud secrets versions add sci-rag-api-keys --data-file=- --project=YOUR_PROJECT
# New secret versions are picked up on the next Cloud Run revision or restart.

URL=$(terraform output -raw service_url)
curl -s $URL/health
curl -s $URL/v1/corpus-manifest -H "X-API-Key: team-key"
curl -s -X POST $URL/v1/query -H "X-API-Key: team-key" \
  -H 'Content-Type: application/json' -d '{"query": "rice straw availability"}'
```

Run the query only after a reviewed corpus-delivery path has populated the database.
Remote agents connect to `$URL/mcp/` with the same API key in the `X-API-Key` header.

## Operating notes

* **Scale to zero** is on (`min_instance_count = 0`). The first request after idle pays a cold start. Set to 1 for an always-warm instance.
* **Schema changes**: rebuild the image, run `terraform apply` (new revision), then run the ops job once. Migrations are additive Alembic revisions following `migrations/versions/0001_initial.py`.
* **External license posture**: if the service is public-facing, require clients to pin `license_classes` to `["public", "open_commercial"]`. Create keys with `corpus:read` omitted for outsiders.
* **Teardown**: `terraform destroy`. Deletion protection is on by default. Pass `-var deletion_protection=false` first.

<div class="srag-checkpoint" markdown>
**Checkpoint: the infrastructure and schema are ready**

`/health` reports a healthy service and `/v1/corpus-manifest` answers with the
configured API key. A cited answer and a nonempty manifest remain unverified until the
corpus-delivery route in issue #189 is qualified.
</div>

## Next steps

- Lock down what an external caller can reach: [Scope precedes ranking](methodology.md#7-scope-precedes-ranking)
- Back up the Cloud SQL instance before the first migration: [Operate a live corpus](operations.md)
- Wire a client to the deployed endpoints: [REST, MCP, and Python API](api.md)
