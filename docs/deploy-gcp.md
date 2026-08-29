---
title: Deploy on Google Cloud
description: Provision Cloud SQL and Cloud Run from the included Terraform, then verify the running service end to end.
---

# Deploy on Google Cloud

By the end of this guide the same service you have been running locally is on
Cloud Run, backed by Cloud SQL with pgvector, reachable by REST and MCP
clients, and destroyable in one command.

<div class="srag-meta-strip">
  <div><strong>You'll build</strong>One Cloud Run service and one Cloud SQL instance</div>
  <div><strong>You'll need</strong>A Google Cloud project and billing enabled</div>
  <div><strong>Time</strong>About 45 minutes, most of it waiting</div>
  <div><strong>Cost</strong>Tens of dollars a month while it is up</div>
  <div><strong>Tested with</strong>v0.3</div>
</div>

!!! note "Optional, and you may have declined it"

    `infra/terraform/` is one of the optional pieces the setup wizard asks
    about. If you answered no to `include_terraform`, the directory and its
    CI job are not in your project. Copy them from
    [the template](https://github.com/sustainability-software-lab/sci-rag-kit/tree/main/infra/terraform)
    if you want them back.

The kit ships a small, honest Terraform module (`infra/terraform/`) that
stands up a production-shaped instance. You get Cloud SQL Postgres with
pgvector, one Cloud Run service serving REST and MCP, one Cloud Run job
for migrations and ingestion, a corpus bucket, secrets, and a
least-privilege service account. This page walks it end to end.

!!! warning "The development database is a different module"

    `infra/terraform/dev-database/` provisions a shared, pausable development
    instance for laptop access through the Cloud SQL Auth Proxy. It disables
    backups and deletion protection by default and creates workspace-scoped
    databases dynamically. Never point a deployment at it. This page and the
    parent `infra/terraform/` module remain the production-shaped path.

Two honest notes before you start. First, this costs money while it
exists. The database is the steady cost, since the default `db-g1-small`
tier runs a few tens of dollars a month, so tear down experiments with
`terraform destroy`. Second, everything here is also doable by hand in the
console. The Terraform is 300 readable lines, and reading it **is** the
architecture documentation.

## Before you start

* A Google Cloud project with billing, and `gcloud` authenticated
  (`gcloud auth login` plus `gcloud auth application-default login`).
* APIs enabled once per project:

```bash
gcloud services enable run.googleapis.com sqladmin.googleapis.com \
  secretmanager.googleapis.com artifactregistry.googleapis.com \
  aiplatform.googleapis.com --project=YOUR_PROJECT
```

* Terraform 1.5+.

## Step 1: build and push the image

```bash
gcloud artifacts repositories create sci-rag --repository-format=docker \
  --location=us-central1 --project=YOUR_PROJECT   # once

gcloud builds submit --project=YOUR_PROJECT \
  --tag us-central1-docker.pkg.dev/YOUR_PROJECT/sci-rag/sci-rag:v1 .
```

The Dockerfile packages the kit, your `domain/` folder, and the
migrations, so the same image serves the API and runs schema upgrades.
Rebuild and repush whenever your domain or corpus manifest changes.

## Step 2: terraform apply

```bash
cd infra/terraform
terraform init
terraform apply \
  -var project_id=YOUR_PROJECT \
  -var image=us-central1-docker.pkg.dev/YOUR_PROJECT/sci-rag/sci-rag:v1
```

What you get, and the security posture you get it with:

* The database is reachable only through the Cloud SQL connector (the
  service and job mount it as a unix socket); no open TCP.
* The runtime service account holds exactly `cloudsql.client`,
  `aiplatform.user`, and read access to its two secrets.
* The Cloud Run service is **not** public by default. Flip
  `-var allow_unauthenticated=true` when you want the app's own API keys
  to be the only gate.

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

A corpus too large to bake into the image has two routes. Upload the
documents to the created bucket and extend your manifest workflow to pull
from it. Or run ingestion from your laptop against the database through
the
[Cloud SQL Auth Proxy](https://cloud.google.com/sql/docs/postgres/connect-auth-proxy),
which needs the `db_connection_name` output.

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

* **Scale to zero** is on (`min_instance_count = 0`); the first request
  after idle pays a cold start. Set it to 1 for a always-warm instance.
* **Schema changes**: rebuild the image, `terraform apply` (new
  revision), run the ops job once. Migrations are additive Alembic
  revisions; write them the way `migrations/versions/0001_initial.py`
  models.
* **External license posture**: if the service is public-facing, make
  your clients pin `license_classes` to `["public", "open_commercial"]`,
  and consider keys whose scope list omits `corpus:read` for outsiders.
* **Teardown**: `terraform destroy` (the database has deletion
  protection on by default; flip `-var deletion_protection=false`
  first when you really mean it).

<div class="srag-checkpoint" markdown>
**Checkpoint: the deployed service answers**

A `POST /v1/query` against the Cloud Run URL returns scoped results with
citations, `/v1/corpus-manifest` lists the documents you ingested, and
`terraform destroy` is a command you have read and understood before you need
it.
</div>

## Next steps

- Lock down what an external caller can reach: [Evidence and rights](evidence-and-rights.md)
- Back up the Cloud SQL instance before the first migration: [Operate a live corpus](operations.md)
- Wire a client to the deployed endpoints: [REST, MCP, and Python API](api.md)
