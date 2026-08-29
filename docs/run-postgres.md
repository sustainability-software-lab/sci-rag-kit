---
title: Run Postgres your way
description: Get a PostgreSQL server with pgvector for Sci RAG Kit through Docker, a local installation, or a shared Cloud SQL development instance.
---

# Run Postgres your way

Sci RAG Kit needs a PostgreSQL server with the pgvector extension. This page covers every supported way to get one, including three paths that need no Docker.

<div class="srag-meta-strip">
  <div><strong>You'll build</strong>A running Postgres 16 to 18 with pgvector</div>
  <div><strong>You'll need</strong>A project checkout</div>
  <div><strong>Time</strong>About 5 minutes</div>
  <div><strong>Tested with</strong>v0.3</div>
</div>

## Before you start

| Requirement | Why | Check |
|---|---|---|
| A Sci RAG Kit checkout or generated project | `make setup` and `.env.example` live in it | `ls Makefile` |
| Your environment manager | It decides which path below is yours | You chose it when the project was created |
| One of: Docker, conda-forge, an existing server, or Cloud SQL | The four supported sources | See the table |

## Pick your path

Your environment manager decides this, so there is only one question to answer.

| If your project uses | Do this | Why |
|---|---|---|
| **uv** or **venv + pip** | [Docker](#run-postgres-in-docker), [a server you already run](#point-at-a-server-you-already-run), or [Cloud SQL](#share-a-cloud-sql-development-instance) | PyPI ships no PostgreSQL server, so these managers need an external source |
| **pixi** or **conda** | [Run it from conda-forge](#run-postgres-from-conda-forge), or [use Cloud SQL](#share-a-cloud-sql-development-instance) | The channel already supplies the fastest local path, while Cloud SQL provides a shared managed instance |

If you have Docker and no strong opinion, use Docker. It is the path CI proves on every change, and the one the [quickstart](quickstart.md) assumes.

## Run Postgres in Docker

The default. `make setup` starts the compose service, installs the project, and applies every migration:

```console title="Terminal"
$ make setup
```

The container listens on host port `5433`, which is the address `.env.example` already carries, so there is no connection string to edit.

**Expected output**

```text
Database schema is up to date.
```

Stop it again when you are done:

```console title="Terminal"
$ make db-down
```

<div class="srag-checkpoint" markdown>
**Checkpoint: the database is reachable**

Run `uv run sci-rag doctor`. The database and schema checks should both report healthy. An empty corpus is still fine at this point.
</div>

## Run Postgres from conda-forge

For pixi and conda projects there is nothing extra to install. Both managers declare `postgresql` and `pgvector` in the project manifest, so `make setup` starts a server from conda-forge in place of a container:

```console title="Terminal"
$ make setup
```

The data lives in `.pgdata/` inside the project, and the server listens on `127.0.0.1:5433`, the same address the container used. Nothing to configure.

```console title="Terminal"
$ make db-down
```

This is a development database: loopback only, trust authentication, run by `scripts/local_postgres.py`. It is not a deployment path. To deploy, see [Deploy on Google Cloud](deploy-gcp.md).

<div class="srag-checkpoint" markdown>
**Checkpoint: the server is yours, not Docker's**

`ls .pgdata` should show a data directory. `uv run sci-rag doctor` should report the same healthy database as the Docker path, because from the kit's side nothing has changed.
</div>

## Share a Cloud SQL development instance

The opt-in Cloud SQL backend works with every environment manager. It gives each workspace a separate development database, destructive-test database, proxy process, and loopback port on one shared instance. Select it when the setup wizard asks whether to include a cloud development database, or use the module in this checkout.

The backend needs the Google Cloud CLI, Terraform, the Cloud SQL Auth Proxy, and `psql`. Authenticate `gcloud`, then provision the development-only instance:

```console title="Terminal"
$ cd infra/terraform/dev-database
$ terraform init
$ terraform apply -var "developer_principal=user:$(gcloud config get account)"
$ terraform output -raw sci_rag_cloud_pg_config
$ cd ../../..
```

Export the four non-secret `SCI_RAG_CLOUD_PG_*` lines printed by Terraform, or add them to your shell profile. Start the workspace proxy and databases, then ask the helper for the connection URLs:

```console title="Terminal"
$ SCI_RAG_DB_BACKEND=cloud make db-up
$ python scripts/cloud_postgres.py config
```

Copy the printed `SCI_RAG_DATABASE_URL=...` line into `.env`. It contains no password. The URL points asyncpg at the mode-0600 pgpass file under `.cloudsql/`. Apply the schema after the URL is set:

```console title="Terminal"
$ SCI_RAG_DB_BACKEND=cloud make setup
```

The helper resumes a paused instance, creates both workspace databases, starts the proxy, and enables pgvector. `make db-down` stops only this workspace's proxy. Pause and resume affect every workspace on the shared instance, so use them only when the other users are finished:

```console title="Terminal"
$ python scripts/cloud_postgres.py pause
$ python scripts/cloud_postgres.py resume
```

For integration and server tests, export only the workspace-scoped test URL. Those suites destroy data in that database:

```console title="Terminal"
$ export SCI_RAG_TEST_DATABASE_URL="$(python scripts/cloud_postgres.py config | \
    sed -n 's/^SCI_RAG_TEST_DATABASE_URL=//p')"
$ uv run pytest tests/integration tests/server -q
```

The development instance has a public IPv4 endpoint with no authorized networks. Connections go through the IAM-authorized, TLS-encrypted Cloud SQL Auth Proxy. This instance has development cost and durability settings and must not serve a deployment. [ADR 0009](adr/0009-cloud-dev-database.md) records the security, permissions, latency, and cost decisions.

<div class="srag-checkpoint" markdown>
**Checkpoint: this workspace owns its local proxy state**

`python scripts/cloud_postgres.py status` should name this workspace's port and database. `uv run sci-rag doctor` should report a healthy database and schema.
</div>

## Point at a server you already run

Any supported server works: a lab machine, a managed instance, a Postgres you keep for something else. Give it three things.

1. **Install pgvector**, if the server does not already have it. On a managed service this is usually an extension you enable; on your own machine it is a package.

2. **Set the connection string** in your local environment file:

    ```dotenv title="~/.env"
    SCI_RAG_DATABASE_URL=postgresql+asyncpg://user:password@host:5432/sci_rag
    ```

3. **Install the project and create the schema.** These are the two steps of `make setup` that are not about starting a container:

    ```console title="Terminal"
    $ uv sync
    $ uv run sci-rag db upgrade
    ```

The kit creates the `vector` extension itself on first migration, so the role you connect as needs permission to do that, or an administrator has to create it once ahead of you.

<div class="srag-checkpoint" markdown>
**Checkpoint: the schema is on the right server**

`uv run sci-rag doctor` should report a healthy database. If it reports the wrong host, `.env` is being shadowed by a `SCI_RAG_DATABASE_URL` already exported in your shell, which wins over the file.
</div>

## Supported versions

Supported servers are **PostgreSQL 16 through 18**. CI proves 16 through the container image on every change, and 18 through the conda-forge path on both Linux and Apple silicon, so both ends of the range are tested. [ADR 0008](adr/0008-supported-postgresql-versions.md) records why the range exists and what would narrow it.

Nothing in the schema depends on a particular major: one HNSW index, no pgvector feature newer than 0.5, and no version-specific SQL. If you are on 15 it will probably work, and nothing tests it, so the project does not claim it.

## Test databases are destructive

The integration and server suites drop and recreate application tables in the database named by `SCI_RAG_TEST_DATABASE_URL`, and truncate them between tests. Point it at a disposable database and nothing else. Never a development corpus, a shared server, or anything deployed.

```dotenv title="~/.env"
SCI_RAG_TEST_DATABASE_URL=postgresql+asyncpg://sci_rag:sci_rag@localhost:5433/sci_rag_test
```

## Next steps

- Ingest the demo corpus and inspect retrieval: [Quickstart](quickstart.md)
- Diagnose a database that will not come up: [Troubleshooting](troubleshooting.md)
- Back up, snapshot, and restore a corpus you care about: [Operate a live corpus](operations.md)
