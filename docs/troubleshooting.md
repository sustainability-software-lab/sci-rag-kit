---
title: Troubleshooting
description: Diagnose Sci RAG Kit setup, database, credential, parsing, retrieval, scope, and serving problems from the observed symptom.
---

# Troubleshooting

Every entry starts from a visible symptom and ends at the command that fixes it. Work from the symptom map and the kit will tell which layer is missing.

<div class="srag-meta-strip">
  <div><strong>You'll build</strong>A diagnosis, from a symptom to its cause</div>
  <div><strong>You'll need</strong>The failing command and its output</div>
  <div><strong>Time</strong>Usually under 5 minutes</div>
  <div><strong>Tested with</strong>v0.4</div>
</div>

## Before you start

Run the kit's own diagnosis first.

```console title="Repository root"
$ uv run sci-rag doctor
```

`doctor` checks configuration, domain validation, database connectivity, migrations, corpus state, graph state, and credentials. It spends no model tokens. Add `--probe` for one live embedding and generation round trip on top.

<div class="srag-checkpoint" markdown>
**Checkpoint: identify the failing layer**

`doctor` names the failing check. Take that name to the symptom map below. If every check is healthy and the behavior is still wrong, the problem is in the domain profile, not in the plumbing.
</div>

## Fast symptom map

| Symptom | Most likely check | First action |
|---|---|---|
| Setup shows numbered prompts instead of arrow-key menus | Terminal capability check selected the plain prompt layer | Continue, or pass `--no-tty` when you want that behavior explicitly |
| New-project credential check fails | The key, project, ADC session, or provider request was rejected | Use the recovery menu before the template download |
| Connection refused on port 5433 | Selected backend is down or the URL differs | `SCI_RAG_DB_BACKEND=<docker|local|cloud> make db-up` |
| Relation or table does not exist | Migrations have not run | `uv run sci-rag db upgrade` |
| No Google credentials configured | The command needs a real model | Configure AI Studio or Vertex, or use offline retrieval |
| Retrieval returns no items | Empty corpus, restrictive scope, or failed stages | `sci-rag stats`, then inspect stage traces |
| `community` says `skipped` | Any rights or metadata filter is active | Expected: stored summaries cannot be safely post-filtered |
| PDF text or tables are mangled | The pypdf fallback handled a difficult file | `uv sync --extra docling`, then re-ingest changed content |
| Ingest says `skipped_duplicate` | The normalized content hash already exists | No action unless the source content changed |
| Embedding dimension mismatch | Model/dimension changed after schema creation | Plan a migration and re-embedding pass |
| API returns 401 or 403 | Missing key, unknown key, or missing scope | Check `SCI_RAG_API_KEYS` and the stable error `code` |
| One retrieval layer timed out | That stage exceeded the profile timeout | Read `traces` and `degraded_stages`; the request intentionally survived |
| Crossref enrichment reports a failure | Network, rate limit, or malformed work metadata | Retry the bounded set; failed documents keep their prior metadata |

## Setup prompts look different

The setup flow uses arrow-key menus when the terminal supports them. It falls back to numbered prompts when input or output is not a TTY, `NO_COLOR` is set, `TERM` is blank or `TERM=dumb`, or the prompt library cannot load. The questions, defaults, validation, and files are identical in both presentations.

Pass `--no-tty` to `sci-rag new` or `sci-rag init` to force the numbered form even in a supported terminal. Pressing Ctrl-C cancels setup instead of treating the interruption as an answer.

## Postgres is unreachable

First identify the backend your project would start:

The default is `docker` in uv and venv + pip projects, and `local` in pixi and conda projects:

```console
$ make -n db-up
```

### Docker

Confirm the container and port before changing configuration:

```console
$ docker compose ps
$ docker compose up -d --wait
$ uv run sci-rag db upgrade
```

The compose service maps PostgreSQL to host port `5433`. Compose scopes the container, network, and volume to the project directory, so several projects can each keep their own database. The host port is machine-wide, so only one project can use `5433` at a time.

If `docker compose up` reports that the port is already allocated, either stop the other project's database with `make db-down` there, or give this project a free port. Publishing a different port requires two matching edits:

```yaml title="~/docker-compose.yml"
    ports:
      - "5434:5432"
```

```dotenv title="~/.env"
SCI_RAG_DATABASE_URL=postgresql+asyncpg://sci_rag:sci_rag@localhost:5434/sci_rag
```

Run `make db-up` again. `docker compose ps` shows the port Compose actually published, which `SCI_RAG_DATABASE_URL` must match.

### Local or system PostgreSQL

For PostgreSQL 16 through 18 (including Postgres.app with pgvector), add `initdb`, `pg_ctl`, and `psql` to PATH:

```console
$ SCI_RAG_DB_BACKEND=local make db-up
$ python scripts/local_postgres.py status
```

Postgres.app 16 normally needs this PATH entry:

```console
$ export PATH="/Applications/Postgres.app/Contents/Versions/16/bin:$PATH"
```

<!-- BEGIN GENERATED PROJECT FEATURE: cloud-helper -->
### Cloud SQL

`start` resumes a paused instance before creating databases or starting the workspace proxy. `resume` changes the instance activation policy; it does not start this workspace proxy. Inspect the helper without exposing its cached password:

```console
$ uv run python scripts/cloud_postgres.py config
$ uv run python scripts/cloud_postgres.py status
$ tail -n 40 .cloudsql/proxy.log
```

The helper chooses a dynamic port at or above `SCI_RAG_CLOUD_PG_PORT`. Copy the current URL from `config`. Do not assume the first port remained available.

If the password secret was rotated, run `stop`, move `.cloudsql/password` and `.cloudsql/pgpass` to a private backup, then run `start`. Never paste either file into an issue.

Missing `gcloud`, `cloud-sql-proxy`, or `psql` fails before the helper changes anything. Authentication errors need `gcloud auth application-default login`. Permission failures name the rejected Cloud SQL or Secret Manager operation. A stale port or proxy PID stays in `.cloudsql/`. Inspect `proxy.log`, stop the matching process through the helper, and run `start` again.
<!-- END GENERATED PROJECT FEATURE: cloud-helper -->

`SCI_RAG_DB_BACKEND` chooses what `make db-up` runs. It does not rewrite application configuration. For Cloud SQL or any external service, set the full passwordless async SQLAlchemy URL printed by `config` as `SCI_RAG_DATABASE_URL`. Set `SCI_RAG_TEST_DATABASE_URL` separately before running destructive database tests.

**Expected output**

```text
Database schema is up to date.
```

If the selected backend is healthy but `doctor` cannot connect, compare `.env` with the helper's current configuration. A copied port, a different workspace database, or stale proxy state indicate common mismatches.

## A command needs model credentials

Three modes are supported:

- `SCI_RAG_GOOGLE_API_KEY`: Google AI Studio.
- `SCI_RAG_GCP_PROJECT` plus Application Default Credentials: Vertex AI.
- `SCI_RAG_EMBEDDING_PROVIDER=local-hash`: offline, deterministic retrieval mechanics only.

The offline embedder is lexical, not semantic. It does not enable graph extraction, HyDE, community summarization, answer generation, or LLM reranking. A refusal at that boundary is correct behavior.

Use `uv run sci-rag doctor --probe` after configuring a credential. The probe spends one small request and distinguishes a present-looking credential from one the provider accepts.

### Recover during project setup

`sci-rag new` checks an entered Google credential with one small model request and a 15-second deadline before downloading the template. A failed check uses actionable, safe error text and never prints the raw provider exception or credential value. Three choices follow:

1. **Try a different credential** to replace the current key or project and run the check again.
2. **Switch to an AI Studio key** to leave the Vertex path and enter a key from [Google AI Studio](https://aistudio.google.com/apikey).
3. **Continue without a model** to finish with the worked example ontology.

The third choice keeps your chosen credential mode and writes the entered key or project to `.env`. It skips only the ontology draft. Fix the credential or run `gcloud auth application-default login` later without rebuilding. Run `uv run sci-rag doctor --probe` after the fix.

The `--no-preflight` flag skips the preliminary model request. It is only available on `sci-rag new`. This escape hatch does not validate the credential. An ontology draft can still call the provider later when a value was entered. Use it only when the preliminary probe itself is the problem, then run `uv run sci-rag doctor --probe` from the generated project.

### Running offline on purpose

A project that sets `SCI_RAG_EMBEDDING_PROVIDER=local-hash` and leaves `SCI_RAG_LLM_MODEL` at its shipped default is a supported mode, not a half-finished setup. The setup wizard writes exactly that for `credentials: offline`. `doctor` reports unavailable generation features as warnings and exits `0`. A passing run means the offline pipeline is healthy.

Retrieval in an offline project reports model-only layers as `disabled`, not `error`. Graph and HyDE ask a model about every query, so a project with no credential cannot run them. `disabled` is the status for a layer this project does not have. `error` is reserved for a layer that should have worked. Vector, keyword, and community retrieval run normally.

Reaching for a model with no credential is still a failure. `doctor` reports `FAIL` when the Google embedding provider is selected without credentials, or when a generation model is named explicitly (such as `SCI_RAG_LLM_MODEL=anthropic:claude-opus-5`) with no key or project. Writing a model id signals intent to generate. The diagnosis follows the configuration.

## Graph extraction reports a failed batch

`sci-rag graph extract` sends chunks to the model in batches. When a response is unusable (usually cut off at the output cap), the command retries the same chunks at half the batch size, down to one chunk. Halving is what can work: an identical rerun gets identical truncation.

A chunk that still fails alone keeps no extraction stamp, so a later run picks it up again. The log records each attempt with a batch identifier and the size tried, with no chunk text.

If a single chunk keeps failing, look at the chunk itself. An unusually long passage or one with heavy markup is the common cause. Use `--batch-size` to start smaller or `--max-chunks` to limit a trial run.

## Retrieval is empty or unexpectedly narrow

Check in this order:

1. `uv run sci-rag stats` confirms documents and chunks exist.
2. The result `traces` show which stages were `success`, `empty`, `skipped`, `timeout`, or `error`. `timeout` is not about the corpus. Raise `SCI_RAG_PROVIDER_CALL_TIMEOUT_S` when the slow part is an embedding or generation call rather than a database query.
3. Remove filters one family at a time: year, author/journal/DOI, source, then license.
4. Confirm that an explicit empty `license_classes` list was not sent. Empty means deny all by design.
5. Use `--profile interactive` to isolate vector and keyword retrieval from model-dependent layers.

Rights and metadata filters run inside each eligible layer before ranking. They can turn a broad question into no result. The community stage always becomes `skipped` for a scoped request because stored community summaries combine multiple documents before request-time scope exists.

!!! scientific "Do not repair an empty result by widening rights silently"
    If the requested license scope contains no supporting document, return no evidence or ask for an explicitly wider scope. Treating `unknown` as public would be a rights failure, not a recall improvement.

## A PDF parses badly

The base install uses pypdf as a lightweight fallback. Docling adds table structure and stronger layout parsing:

```console
$ uv sync --extra docling
$ uv run sci-rag ingest --manifest path/to/manifest.jsonl
```

An identical source will still deduplicate. Remove the previously ingested document before replacing its stored parse. See [Operate a live corpus](operations.md) for snapshots and backups to take first.

## Embeddings no longer match

Every chunk carries an embedding version, and the database column has a fixed dimension. Use the planner before acting:

```console
$ uv run sci-rag embed reindex --dry-run
```

Same-dimension model changes can be re-embedded in place. Cross-dimension changes require a schema migration because pgvector enforces the column width. Do not mix vector dimensions on a populated database.

## The server rejects a request

REST errors use `application/problem+json` with a stable `code` and `X-Request-ID`. Branch on `code`, not the English `detail`. Common authorization codes are `missing_key`, `invalid_key`, and `insufficient_scope`. Throttling is `rate_limited` and includes `Retry-After`.

With no `SCI_RAG_API_KEYS`, the server runs open and logs a warning. That mode is suitable for localhost only. See the [API authentication contract](api.md#authentication) before exposing a service.

## Still stuck

Capture these without secrets:

```console
$ uv run sci-rag doctor
$ uv run sci-rag stats
$ uv run sci-rag retrieve "a representative question" --profile interactive --limit 3
```

Include the doctor table, stage traces, package version, operating system, and whether Postgres is compose-managed or external. Do not paste `.env`, bearer keys, passwords, or credentials into an issue.

## Next steps

- Nothing here matched: [open an issue](https://github.com/sustainability-software-lab/sci-rag-kit/issues) with the output above
- The database is the problem: [Run Postgres your way](run-postgres.md)
- Retrieval works but the answers are wrong: [Evaluate your pipeline](evaluation.md)
