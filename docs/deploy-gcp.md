---
title: Deploy on Google Cloud
description: Provision Cloud SQL and Cloud Run from the included Terraform, then verify the running service end to end.
---

# Deploy on Google Cloud

By the end, the service runs on Cloud Run backed by Cloud SQL with pgvector, reachable by REST and MCP clients.

<div class="srag-meta-strip">
  <div><strong>You'll build</strong>One Cloud Run service and one Cloud SQL instance</div>
  <div><strong>You'll need</strong>A Google Cloud project and billing enabled</div>
  <div><strong>Time</strong>About 45 minutes, most of it waiting</div>
  <div><strong>Cost</strong>Tens of dollars a month while it is up</div>
  <div><strong>Tested with</strong>v0.4</div>
</div>

!!! note "Optional, and you may have declined it"

    Quick keeps Terraform in the generated project. Run
    `sci-rag new --advanced` for a new project, or `sci-rag init --advanced`
    in a checkout, when you want setup to ask about it. If you answer no to
    `include_terraform`, the directory and its CI job are not in your project.
    Copy them from
    [the template](https://github.com/sustainability-software-lab/sci-rag-kit/tree/main/infra/terraform)
    if you want them back.

The kit ships Terraform (`infra/terraform/`) that provisions a production deployment: Cloud SQL Postgres with pgvector, one Cloud Run service for REST and MCP, one Cloud Run job for migrations and ingestion, a corpus bucket, secrets, and a least-privilege service account.

<!-- BEGIN GENERATED PROJECT FEATURE: cloud-provisioning -->
!!! warning "The development database is a different module"

    `infra/terraform/dev-database/` provisions a shared, pausable development
    instance for laptop access through the Cloud SQL Auth Proxy. The
    `scripts/cloud_postgres.py` helper, not Terraform, creates workspace-scoped
    databases dynamically. The development module disables backups and deletion
    protection by default. Never point a deployment at it. This page uses the production-shaped path.
<!-- END GENERATED PROJECT FEATURE: cloud-provisioning -->

This costs money while it runs. The database is the steady cost: the default `db-g1-small` tier costs tens of dollars a month. Tear down experiments with `terraform destroy`. Everything here is also doable by hand in the console. The Terraform is 300 readable lines; reading it teaches you the architecture.

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

The Dockerfile packages the kit, the `domain/` folder, and migrations. The same image serves the API and runs schema upgrades. Rebuild whenever the domain or corpus manifest changes.

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

## Step 3: migrate, then ingest

```bash
# Create the schema (terraform output prints this exact command):
gcloud run jobs execute sci-rag-ops --region=us-central1 --project=YOUR_PROJECT --wait

# Ingest the corpus baked into the image (the demo, or your own):
gcloud run jobs execute sci-rag-ops --region=us-central1 --project=YOUR_PROJECT \
  --args='ingest,--manifest,data/demo/manifest.jsonl' --wait

# Build the graph:
gcloud run jobs execute sci-rag-ops --region=us-central1 --project=YOUR_PROJECT \
  --args='graph,extract' --wait
gcloud run jobs execute sci-rag-ops --region=us-central1 --project=YOUR_PROJECT \
  --args='graph,communities' --wait
```

For a corpus too large to bake into the image, upload documents to the created bucket and extend the manifest to pull from it. Alternatively, run ingestion from a laptop through the [Cloud SQL Auth Proxy](https://cloud.google.com/sql/docs/postgres/connect-auth-proxy), using the `db_connection_name` output.

## Step 4: set API keys and verify

```bash
echo '{"team-key": {"scopes": ["retrieval:query", "retrieval:answer", "corpus:read"]}}' | \
  gcloud secrets versions add sci-rag-api-keys --data-file=- --project=YOUR_PROJECT
# New secret versions are picked up on the next Cloud Run revision or restart.

URL=$(terraform output -raw service_url)
curl -s $URL/health
curl -s $URL/v1/corpus-manifest
curl -s -X POST $URL/v1/query -H "Authorization: Bearer team-key" \
  -H 'Content-Type: application/json' -d '{"query": "rice straw availability"}'
```

Remote agents connect to `$URL/mcp/` with the same bearer key.

## Operating notes

* **Scale to zero** is on (`min_instance_count = 0`). The first request after idle pays a cold start. Set to 1 for an always-warm instance.
* **Schema changes**: rebuild the image, run `terraform apply` (new revision), then run the ops job once. Migrations are additive Alembic revisions following `migrations/versions/0001_initial.py`.
* **External license posture**: if the service is public-facing, require clients to pin `license_classes` to `["public", "open_commercial"]`. Create keys with `corpus:read` omitted for outsiders.
* **Teardown**: `terraform destroy`. Deletion protection is on by default. Pass `-var deletion_protection=false` first.

<div class="srag-checkpoint" markdown>
**Checkpoint: the deployed service answers**

A `POST /v1/query` against the Cloud Run URL returns scoped results with
citations, `/v1/corpus-manifest` lists the ingested documents, and
the meaning of `terraform destroy` is clear before it is ever needed.
</div>

## Next steps

- Lock down what an external caller can reach: [Scope precedes ranking](methodology.md#7-scope-precedes-ranking)
- Back up the Cloud SQL instance before the first migration: [Operate a live corpus](operations.md)
- Wire a client to the deployed endpoints: [REST, MCP, and Python API](api.md)
