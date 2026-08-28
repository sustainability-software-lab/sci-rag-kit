---
title: Run Postgres your way
description: Get a PostgreSQL server with pgvector for Sci RAG Kit, with or without Docker, and point the kit at one you already run.
---

# Run Postgres your way

Sci RAG Kit needs exactly one thing from your machine that it cannot install for you: a PostgreSQL server with the pgvector extension. This page covers every supported way to get one, including the two that need no Docker at all.

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
| One of: Docker, conda-forge, or an existing server | The three supported sources | see the table |

## Pick your path

Your environment manager decides this, so there is only one question to answer.

| If your project uses | Do this | Why |
|---|---|---|
| **uv** or **venv + pip** | [Docker](#run-postgres-in-docker), or [a server you already run](#point-at-a-server-you-already-run) | PyPI ships no PostgreSQL server, so neither manager can install one |
| **pixi** or **conda** | [Run it from conda-forge](#run-postgres-from-conda-forge) | The channel ships `postgresql` and `pgvector` together, so it is already in your manifest |

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
