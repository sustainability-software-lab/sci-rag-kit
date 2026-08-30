---
title: Run Postgres your way
description: Choose and operate a supported PostgreSQL server with pgvector for Sci RAG Kit.
---

# Run Postgres your way

Choose one supported PostgreSQL path, start it through the same Make targets,
and keep destructive tests pointed at a disposable database.

<div class="srag-meta-strip">
  <div><strong>You'll build</strong>A running PostgreSQL 16 to 18 with pgvector</div>
  <div><strong>You'll need</strong>A project checkout and one server source</div>
  <div><strong>Time</strong>About 5 minutes locally, longer for first Cloud startup</div>
  <div><strong>Tested with</strong>v0.3</div>
</div>

## Before you start

| Requirement | Why | Check |
|---|---|---|
| A Sci RAG Kit checkout or generated project | `make setup` and the helper scripts live in it | `ls Makefile` |
| One supported environment manager | It supplies the command runner | You chose uv, pixi, conda, or venv + pip during setup |
| PostgreSQL 16 through 18 with pgvector | The application, migrations, and tests all need it | `psql --version` and `CREATE EXTENSION vector` |

`SCI_RAG_DB_BACKEND` controls which backend `make db-up`, `make db-down`, and
`make setup` dispatch to. `SCI_RAG_DATABASE_URL` controls the application
connection. `SCI_RAG_TEST_DATABASE_URL` separately controls the destructive
integration and server suites. Selecting a backend never rewrites either URL.

## Recommended defaults

Docker is the template default and the closest local match to the PostgreSQL 16
service in CI. Generated pixi and conda projects use their bundled conda-forge
server by default. Every manager can select `local` when a supported system
PostgreSQL and pgvector are on `PATH`, including Postgres.app. Every manager can
also retain the optional Cloud helper through Advanced setup. Quick setup
removes that helper from generated projects.

| Environment manager | Recommended default | Other local path | Optional shared path |
|---|---|---|---|
| uv | Docker | system PostgreSQL | Cloud SQL |
| pixi | conda-forge PostgreSQL | Docker or system PostgreSQL | Cloud SQL |
| conda | conda-forge PostgreSQL | Docker or system PostgreSQL | Cloud SQL |
| venv + pip | Docker | system PostgreSQL | Cloud SQL |

## Run Postgres in Docker

If you use the template checkout with no backend override, run:

```console title="Terminal"
$ make setup
```

That synchronizes dependencies, starts the selected database backend, and
applies every migration. Docker is the template default, so this checkout
starts the compose service on host port `5433`.

Stop the selected backend when you are done:

```console title="Terminal"
$ make db-down
```

<div class="srag-checkpoint" markdown>
**Checkpoint: the database is reachable**

Run `uv run sci-rag doctor`. The database and schema checks should report
healthy. An empty corpus is fine at this point.
</div>

## Run Postgres from conda-forge

Generated pixi and conda projects declare `postgresql` and `pgvector` in their
manifest. Their rewritten `make setup` starts `scripts/local_postgres.py`, not
the compose service:

```console title="Terminal"
$ make setup
```

The helper keeps data under `.pgdata/`, listens on loopback, and uses trust
authentication. This is a machine-local development server and never a
deployment path.

```console title="Terminal"
$ make db-down
```

<div class="srag-checkpoint" markdown>
**Checkpoint: the server came from the selected manager**

`ls .pgdata` should show the data directory. `uv run sci-rag doctor` should
report a healthy database and current schema.
</div>

## Point at a system PostgreSQL

Any environment manager can use `local` when `initdb`, `pg_ctl`, and `psql`
from PostgreSQL 16 through 18 are on `PATH`. Postgres.app is one supported
source on macOS. Add its versioned `bin` directory to `PATH`, then run:

```console title="Terminal"
$ SCI_RAG_DB_BACKEND=local make setup
```

The helper creates the `sci_rag` development database and enables pgvector.
You may also operate an existing compatible server yourself. In that case, set
the application URL and run only dependency synchronization plus migrations:

```dotenv title="~/.env"
SCI_RAG_DATABASE_URL=postgresql+asyncpg://user:password@host:5432/sci_rag
```

```console title="Terminal"
$ uv sync
$ uv run sci-rag db upgrade
```

<div class="srag-checkpoint" markdown>
**Checkpoint: the schema is on the intended server**

`uv run sci-rag doctor` should report the expected host and a current schema.
An exported URL takes precedence over the value in `.env`.
</div>

<!-- BEGIN GENERATED PROJECT FEATURE: cloud-helper -->
## Share a Cloud SQL development instance

The optional Cloud helper gives each workspace a development database, a
disposable test database, a proxy process, and a dynamic loopback port on one
shared instance. Quick keeps the default and removes it. For a new generated project, choose
`sci-rag new --advanced`; for a checkout, choose `sci-rag init --advanced`.
The helper is a development path and not the production deployment module.
<!-- END GENERATED PROJECT FEATURE: cloud-helper -->

<!-- BEGIN GENERATED PROJECT FEATURE: cloud-provisioning -->
## One-time Cloud SQL provisioning

An operator performs this stage once. You need billing, `gcloud`, Application
Default Credentials, Terraform, the Cloud SQL Auth Proxy, and `psql`. The
operator also needs permission to create and update the Cloud SQL instance,
create databases, connect through the proxy, read the generated password
secret, and manage the scoped IAM bindings. Cloud SQL Editor plus access to the
one Secret Manager secret covers the helper's current operations.

Authenticate, then apply the development-only module with an explicit project:

```console title="Terminal"
$ gcloud auth login
$ gcloud auth application-default login
$ cd infra/terraform/dev-database
$ terraform init
$ terraform plan -out=dev-database.tfplan \
    -var "project_id=YOUR_PROJECT" \
    -var "instance_name=YOUR_INSTANCE" \
    -var "developer_principal=user:YOUR_EMAIL"
$ terraform show dev-database.tfplan     # read it before you apply it
$ terraform apply dev-database.tfplan
$ terraform output -raw sci_rag_cloud_pg_config
$ cd ../../..
```

Replace all three placeholders. `project_id` and `instance_name` have no
defaults, so Terraform stops at input validation if you omit either one,
before it reads state or plans a change. That is deliberate: a module that
guessed either value could aim a change at an instance you never named.

Read the saved plan before applying it. Every line should be a create. A
change or a destroy on an instance you did not expect means the inputs point
somewhere you did not intend, and applying anyway is how shared infrastructure
gets reconciled by accident.

Terraform prints only non-secret helper settings, but Terraform state contains
the generated database password. Store the state as a credential and never
commit or paste it into an issue.

Advanced setup lets a generated project retain the helper while declining the
Terraform tree. That helper-only project has no provisioning module. Connect it
to an existing compatible instance or copy the development module from the
upstream template before provisioning.

<div class="srag-checkpoint" markdown>
**Checkpoint: provisioning returned helper configuration**

The output names the project, instance, region, and database user. It contains
no database password.
</div>
<!-- END GENERATED PROJECT FEATURE: cloud-provisioning -->

<!-- BEGIN GENERATED PROJECT FEATURE: cloud-helper -->
## Start a Cloud SQL workspace

Configure the helper with these inputs. The defaults are the current script
contract, not a reason to omit an explicit project in Terraform.

| Variable | Default | Purpose |
|---|---|---|
| `SCI_RAG_CLOUD_PG_PROJECT` | internal repository default; override required | Google Cloud project containing the instance |
| `SCI_RAG_CLOUD_PG_INSTANCE` | `sci-rag-dev` | Shared development instance name |
| `SCI_RAG_CLOUD_PG_REGION` | `us-west1` | Instance region |
| `SCI_RAG_CLOUD_PG_DIR` | `.cloudsql` | Ignored workspace-local proxy and credential state |
| `SCI_RAG_CLOUD_PG_PORT` | `5433` | First loopback port to try; the helper chooses the next free port |
| `SCI_RAG_CLOUD_PG_WORKSPACE` | current directory name | Suffix for same-basename collision avoidance |
| `SCI_RAG_CLOUD_PG_USER` | `sci_rag` | Shared PostgreSQL role |

The helper normalizes the workspace name into
`sci_rag_<workspace>` and `sci_rag_test_<workspace>`. Override
`SCI_RAG_CLOUD_PG_WORKSPACE` when two checkouts have the same basename. The
database pair and local proxy state prevent accidental URL and destructive-test
collisions. Every database uses the same PostgreSQL role, so that separation is
not an authorization boundary.

Start the backend and print both secret-free URLs:

```console title="Terminal"
$ SCI_RAG_DB_BACKEND=cloud make db-up
$ uv run python scripts/cloud_postgres.py config
```

`start` resumes a paused instance, creates the development and test databases,
starts the proxy on a free port at or above `5433`, and enables pgvector in
both databases. A paused first start can take several minutes while Cloud SQL
activates. Put both printed URLs in an owner-only `.env`, then run migrations:

```console title="Terminal"
$ chmod 600 .env
$ uv run sci-rag db upgrade
```

<div class="srag-checkpoint" markdown>
**Checkpoint: this workspace owns its proxy state**

`uv run python scripts/cloud_postgres.py status` should name the normalized
database, dynamic port, and running proxy. `uv run sci-rag doctor` should report
a healthy database and schema.
</div>

## Manage the Cloud SQL lifecycle

| Action | Scope and effect |
|---|---|
| `config` | Prints resolved non-secret settings and both passwordless URLs; it starts nothing |
| `start` | Resumes if needed, creates both workspace databases, starts the proxy, and enables pgvector |
| `status` | Reports instance and current workspace proxy state without changing either |
| `stop` | Stops only the current workspace proxy; `make db-down` dispatches here |
| `pause` | Stops this proxy and pauses the shared instance; it affects every workspace |
| `resume` | Changes the shared instance activation policy to running; `start` is still the workspace startup command |

`stop` and Conductor archive do not delete a database. `pause` and `resume`
affect every workspace, so only the shared-instance operator should use them.
Normal workspace cleanup runs `make db-down` and stops only the current
workspace proxy.

The instance has public IPv4 enabled with no authorized networks. Connections
use IAM authorization and TLS through the Cloud SQL Auth Proxy. Backups and
deletion protection are disabled by default. This development instance must not
hold the only copy of a valuable corpus.

## Use Cloud SQL in Conductor workspaces

This optional recipe is user-installed, machine-local configuration. Sci RAG
Kit does not ship it, and Conductor does not enable or write it for you. Store
`.conductor/settings.local.toml` and the wrapper scripts in the Conductor root
clone, not in each worktree. The settings call them through
`$CONDUCTOR_ROOT_PATH`:

```toml title="~/.conductor/settings.local.toml"
"$schema" = "https://conductor.build/schemas/settings.repo.schema.json"

[scripts]
setup = '"$CONDUCTOR_ROOT_PATH/.conductor/setup-cloud-workspace.sh"'
archive = '"$CONDUCTOR_ROOT_PATH/.conductor/archive-cloud-workspace.sh"'
run_mode = "concurrent"

[scripts.run.serve]
command = 'uv run sci-rag serve --port "$CONDUCTOR_PORT"'
available_in = ["local"]
default = true
icon = "play"

[scripts.run.test]
command = '"$CONDUCTOR_ROOT_PATH/.conductor/run-cloud-tests.sh"'
available_in = ["local"]
icon = "test-tube"
```

The setup wrapper synchronizes dependencies, starts or verifies the proxy
through public helper commands, writes both secret-free URLs into an owner-only
`.env`, and applies migrations. Use placeholders for the non-secret Cloud
settings in your shell or settings file:

```bash title="~/.conductor/setup-cloud-workspace.sh"
#!/bin/bash
set -euo pipefail
umask 077
export SCI_RAG_DB_BACKEND=cloud
export SCI_RAG_CLOUD_PG_PROJECT="YOUR_PROJECT"
export SCI_RAG_CLOUD_PG_INSTANCE="YOUR_INSTANCE"
export SCI_RAG_CLOUD_PG_REGION="YOUR_REGION"
export SCI_RAG_CLOUD_PG_USER="YOUR_DATABASE_USER"

uv sync --group docs --group docs-test
make db-up
config="$(uv run python scripts/cloud_postgres.py config)"
dev_url="$(printf '%s\n' "$config" | sed -n 's/^SCI_RAG_DATABASE_URL=//p')"
test_url="$(printf '%s\n' "$config" | sed -n 's/^SCI_RAG_TEST_DATABASE_URL=//p')"
test -n "$dev_url" && test -n "$test_url"

touch .env
chmod 600 .env
tmp="$(mktemp "${TMPDIR:-/tmp}/sci-rag-env.XXXXXX")"
grep -vE '^SCI_RAG_(DATABASE|TEST_DATABASE)_URL=' .env > "$tmp" || true
printf 'SCI_RAG_DATABASE_URL=%s\nSCI_RAG_TEST_DATABASE_URL=%s\n' \
  "$dev_url" "$test_url" >> "$tmp"
mv "$tmp" .env
SCI_RAG_DATABASE_URL="$dev_url" uv run sci-rag db upgrade
```

The test wrapper exports only the disposable test URL to the test process:

```bash title="~/.conductor/run-cloud-tests.sh"
#!/bin/bash
set -euo pipefail
config="$(uv run python scripts/cloud_postgres.py config)"
export SCI_RAG_TEST_DATABASE_URL="$(printf '%s\n' "$config" | \
  sed -n 's/^SCI_RAG_TEST_DATABASE_URL=//p')"
test -n "$SCI_RAG_TEST_DATABASE_URL"
exec uv run pytest "$@"
```

Archive must stop only this workspace proxy. It must not pause the shared
instance or delete any database:

```bash title="~/.conductor/archive-cloud-workspace.sh"
#!/bin/bash
set -euo pipefail
export SCI_RAG_DB_BACKEND=cloud
make db-down
```

<div class="srag-checkpoint" markdown>
**Checkpoint: parallel workspaces stay isolated**

Each workspace `.env` should contain a different normalized development/test
database pair and may use a different proxy port. Archiving one workspace must
leave every other proxy and the shared instance running.
</div>
<!-- END GENERATED PROJECT FEATURE: cloud-helper -->

## Use a disposable test database

The integration and server fixtures drop and recreate application tables in
`SCI_RAG_TEST_DATABASE_URL`, then truncate them between tests. Point that URL
at a disposable database and nothing else. A skipped database suite is not
passing evidence.

```dotenv title="~/.env"
SCI_RAG_TEST_DATABASE_URL=postgresql+asyncpg://sci_rag:sci_rag@localhost:5433/sci_rag_test
```

## Confirm the supported versions

Supported servers are PostgreSQL 16 through 18. CI proves 16 through the
container service and the Docker-free workflow proves the current conda-forge
resolution, PostgreSQL 18, on Linux and Apple silicon. [ADR 0008](adr/0008-supported-postgresql-versions.md)
records the range and its reversal conditions.

## Next steps

- Ingest the demo corpus and inspect retrieval: [Quickstart](quickstart.md)
- Diagnose a database that will not start: [Troubleshooting](troubleshooting.md)
- Back up, snapshot, and restore a corpus: [Operate a live corpus](operations.md)
