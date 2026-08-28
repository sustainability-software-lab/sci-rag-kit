---
title: Troubleshooting
description: Diagnose Sci RAG Kit setup, database, credential, parsing, retrieval, scope, and serving problems from the observed symptom.
---

# Troubleshooting

Every entry on this page starts from a symptom you can see and ends at the one command that fixes it. Work from the symptom map, and let the kit tell you which layer is missing.

<div class="srag-meta-strip">
  <div><strong>You'll build</strong>A diagnosis, from a symptom to its cause</div>
  <div><strong>You'll need</strong>The failing command and its output</div>
  <div><strong>Time</strong>Usually under 5 minutes</div>
  <div><strong>Tested with</strong>v0.3</div>
</div>

## Before you start

Run the kit's own diagnosis first. Guessing a cause from an empty retrieval result is how an afternoon disappears.

```console title="Repository root"
$ uv run sci-rag doctor
```

`doctor` checks configuration, domain validation, database connectivity, migrations, corpus state, graph state, and credentials, and it spends no model tokens doing it. Add `--probe` when you want one live embedding and generation round trip on top.

<div class="srag-checkpoint" markdown>
**Checkpoint: you know which layer is unhappy**

`doctor` names the failing check. Take that name to the symptom map below. If every check is healthy and the behavior is still wrong, the problem is in your domain profile or your seed questions, not in the plumbing.
</div>

## Fast symptom map

| Symptom | Most likely check | First action |
|---|---|---|
| Connection refused on port 5433 | Postgres is down or the URL differs | `docker compose up -d --wait` |
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

## Postgres is unreachable

Confirm the container and port before changing configuration:

```console
$ docker compose ps
$ docker compose up -d --wait
$ uv run sci-rag db upgrade
```

The included compose service maps PostgreSQL to host port `5433`. If you use another server, set the full async SQLAlchemy URL in `SCI_RAG_DATABASE_URL` and ensure the pgvector extension is available.

**Expected output**

```text
Database schema is up to date.
```

If the container is healthy but `doctor` cannot connect, compare `.env` with `docker-compose.yml`; a copied port `5432` is a common mismatch.

## A command needs model credentials

Three modes are supported:

- `SCI_RAG_GOOGLE_API_KEY`: Google AI Studio.
- `SCI_RAG_GCP_PROJECT` plus Application Default Credentials: Vertex AI.
- `SCI_RAG_EMBEDDING_PROVIDER=local-hash`: offline, deterministic retrieval mechanics only.

The offline embedder is lexical, not semantic. It does not make graph extraction, HyDE, community summarization, answer generation, reranking through the LLM adapter, or judged-answer evaluation available. A refusal at that boundary is correct behavior.

Use `uv run sci-rag doctor --probe` after configuring a credential. The probe spends one small request and distinguishes a present-looking credential from one the provider accepts.

### Running offline on purpose

A project that sets `SCI_RAG_EMBEDDING_PROVIDER=local-hash`, configures no credential for any provider, and leaves `SCI_RAG_LLM_MODEL` and its siblings at their shipped defaults is a supported mode, not a half-finished setup. The setup wizard writes exactly that for `credentials: offline`. `doctor` reports the unavailable generation features as warnings and exits `0`, so a green run means the offline pipeline is healthy rather than that a model is reachable.

Reaching for a model with no credential behind it is still a failure. `doctor` reports `FAIL` when the Google embedding provider is selected without credentials, and when a generation model is named explicitly, such as `SCI_RAG_LLM_MODEL=anthropic:claude-opus-5`, with no key or project behind it. Writing a model id is how you say you intend to generate, so the diagnosis follows what the configuration asks for rather than what happens to be missing.

## Retrieval is empty or unexpectedly narrow

Check in this order:

1. `uv run sci-rag stats` confirms documents and chunks exist.
2. The result `traces` show which stages were `success`, `empty`, `skipped`, `timeout`, or `error`.
3. Remove filters one family at a time: year, author/journal/DOI, source, then license.
4. Confirm that an explicit empty `license_classes` list was not sent. Empty means deny all by design.
5. Use `--profile interactive` to isolate vector and keyword retrieval from model-dependent layers.

Rights and metadata filters run inside each eligible layer before ranking. They can legitimately turn a broad question into no result. The community stage always becomes `skipped` for a scoped request because each stored community summary combines multiple documents before request-time scope exists.

!!! scientific "Do not repair an empty result by widening rights silently"
    If the requested license scope contains no supporting document, return no evidence or ask for an explicitly wider scope. Treating `unknown` as public would be a rights failure, not a recall improvement.

## A PDF parses badly

The base install uses pypdf as a lightweight fallback. Docling adds table structure and stronger layout parsing, but brings a larger machine-learning stack:

```console
$ uv sync --extra docling
$ uv run sci-rag ingest --manifest path/to/manifest.jsonl
```

An identical source will still deduplicate. Remove the previously ingested document with the corpus lifecycle commands before replacing its stored parse; the [Operate a live corpus](operations.md) explains snapshots and backups to take first.

## Embeddings no longer match

Every chunk carries an embedding version, and the database column has a fixed dimension. Use the planner before acting:

```console
$ uv run sci-rag embed reindex --dry-run
```

Same-dimension model changes can be re-embedded in place. Cross-dimension changes require a schema migration because pgvector enforces the column width. Do not mix vector dimensions or change `SCI_RAG_EMBEDDING_DIM` on a populated database and hope the provider adapts.

## The server rejects a request

REST errors use `application/problem+json` with a stable `code` and `X-Request-ID`. Branch on `code`, not the English `detail`. Common authorization codes are `missing_key`, `invalid_key`, and `insufficient_scope`; throttling is `rate_limited` and includes `Retry-After`.

With no `SCI_RAG_API_KEYS`, the server deliberately runs open and logs a warning. That mode is suitable for localhost only. See the [API authentication contract](api.md#authentication) before exposing a service.

## Still stuck

Capture these without secrets:

```console
$ uv run sci-rag doctor
$ uv run sci-rag stats
$ uv run sci-rag retrieve "a representative question" --profile interactive --limit 3
```

Include the doctor table, stage traces, package version, operating system, and whether Postgres is compose-managed or external. Never paste `.env`, bearer keys, database passwords, or model credentials into an issue.

## Next steps

- Nothing here matched: [open an issue](https://github.com/sustainability-software-lab/sci-rag-kit/issues) with the output above
- The database is the problem: [Run Postgres your way](run-postgres.md)
- Retrieval works but the answers are wrong: [Evaluate your pipeline](evaluation.md)
