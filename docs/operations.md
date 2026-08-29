---
title: Operate a live corpus
description: Back up, restore, snapshot, delete, garbage-collect, and re-embed a corpus that keeps changing under a running service.
---

# Operate a live corpus

Everything the kit knows lives in one Postgres database, which keeps the
operational discipline short. Snapshot what the corpus **is**, back up what
the database **holds**, and rehearse the restore before you need it.

<div class="srag-meta-strip">
  <div><strong>You'll build</strong>A backup, a restore drill, and a snapshot habit</div>
  <div><strong>You'll need</strong>Database access and `pg_dump`</div>
  <div><strong>Time</strong>About 30 minutes for the first pass</div>
  <div><strong>Tested with</strong>v0.3</div>
</div>

## Before you start

| Requirement | Why | Check |
|---|---|---|
| A corpus worth protecting | Most of this page is unnecessary on the demo fixture | `uv run sci-rag stats` |
| `pg_dump` and `psql` on your path | The backup and restore paths are ordinary Postgres tools | `pg_dump --version` |
| Somewhere to put a dump that is not the database host | A backup on the same disk is not a backup | |
| A disposable database for the restore drill | You are going to restore into it, and it will be overwritten | |

## Crossref enrichment and retraction review

After ingesting DOI-bearing papers, preview the Crossref enrichment set:

```bash
uv run sci-rag corpus enrich --mailto you@example.org --dry-run
```

The dry run makes no network calls and writes nothing. Apply it by removing
`--dry-run`; `--limit N` bounds a trial. The client identifies your contact
address to Crossref's polite pool, rate limits requests, retries 429 and 5xx
responses, and records failures per document. A later run skips metadata
refreshed in the last 30 days.

The command stores citation count, journal, normalized reference DOIs,
enrichment time, and explicit
Crossref retraction assertions in `documents.extra`, while also promoting
journal to its indexed column. Both current `updated-by` responses and the
`update-to` shape used by Retraction Watch records are recognized. The kit
does not infer retraction from titles or missing fields.

Preview the corpus-local citation reconciliation, then apply it:

```bash
uv run sci-rag graph citations --dry-run
uv run sci-rag graph citations --apply
```

Resolved rows connect two present corpus documents. References whose DOI is
not yet in the corpus stay as null-target pointers and resolve on a later run
after that document is ingested. Self-references and duplicate DOI references
do not become edges. `corpus delete` cascades affected pointers, while
`sci-rag graph gc` reports and removes any dangling rows found defensively.

Run `uv run sci-rag doctor` afterwards. A retraction warning gives the known
count. Answering excludes those documents by default, while raw retrieval
does not change. Review the flagged records and use `sci-rag corpus delete`
when they should leave the corpus.

## Corpus snapshots (identity, not backup)

```bash
uv run sci-rag corpus snapshot v0.2-demo
```

writes `data/snapshots/v0.2-demo.json`: document counts, per-document
content hashes, embedding versions, the git commit, and a single
`corpus_digest` (SHA-256 over the sorted content hashes). Two corpora
with the same digest hold the same documents, whatever their ids or
ingestion order.

Snapshots are small, immutable (a name refuses to be overwritten), and
safe to commit next to eval evidence. Reference them from eval runs:

```bash
uv run sci-rag eval retrieval --ablation --snapshot v0.2-demo
```

and the report JSON carries the snapshot name, so a reader can check
later that the numbers were measured on exactly that corpus. A snapshot
records identity; it does not contain the data. Backup does.

## Backup

### Local or self-hosted Postgres

```bash
# Plain-format dump of the whole knowledge base (schema + data).
pg_dump "$SCI_RAG_DATABASE_URL_SYNC" --format=custom \
  --file "sci-rag-$(date +%Y%m%d).dump"
```

(`pg_dump` speaks the sync driver URL: strip the `+asyncpg` marker,
e.g. `postgresql://sci_rag:sci_rag@localhost:5433/sci_rag`.)

The pgvector extension types are included in the dump; the restore
target needs the extension available (`CREATE EXTENSION vector` runs in
migration 0001, and `pg_restore` recreates it from the dump).

### Cloud SQL (the deploy-gcp.md path)

Prefer managed backups over hand-run dumps:

```bash
gcloud sql backups create --instance=YOUR_INSTANCE --project=YOUR_PROJECT
gcloud sql backups list --instance=YOUR_INSTANCE --project=YOUR_PROJECT
```

Enable automated daily backups plus point-in-time recovery on the
instance; the Terraform module in `infra/` exposes both flags. Take a
manual backup before every schema migration and every bulk operation
(delete campaigns, re-embed runs).

<!-- BEGIN GENERATED PROJECT FEATURE: cloud-helper -->
The optional development Cloud SQL helper is a different path. Its instance
has no backup guarantee, and backups plus deletion protection are disabled by
default. Do not store the only copy of a valuable corpus there. Export or dump
anything you need to keep before an operator pauses or replaces the instance.
<!-- END GENERATED PROJECT FEATURE: cloud-helper -->

## Restore drill

Rehearse this before an incident, on a scratch database:

```bash
createdb sci_rag_restore
pg_restore --dbname "postgresql://sci_rag:sci_rag@localhost:5433/sci_rag_restore" \
  --no-owner "sci-rag-20260827.dump"

# Point the kit at the restored copy and verify:
SCI_RAG_DATABASE_URL="postgresql+asyncpg://sci_rag:sci_rag@localhost:5433/sci_rag_restore" \
  uv run sci-rag doctor
```

`doctor` checks schema revision, pgvector, corpus counts, and embedding
versions in one pass. Then compare identity against the snapshot you
took at backup time:

```bash
SCI_RAG_DATABASE_URL=... uv run sci-rag corpus snapshot restore-check
# corpus_digest in data/snapshots/restore-check.json must equal the
# digest in the snapshot taken when the backup was made.
```

Cloud SQL restores follow the console or
`gcloud sql backups restore`; run the same doctor + snapshot-digest
verification afterwards.

## Analytical export

For sharing data outside Postgres, or for belt-and-suspenders archival:

```bash
sci-rag corpus export export/                      # JSONL, no extra dependency
sci-rag corpus export export/ --format parquet     # needs `uv sync --extra export`
```

One file per table: `documents`, `chunks`, `entities`, `relationships`.
Chunk embeddings are omitted by default because they dominate the output
size and are rarely what a downstream consumer wants; `--include-embeddings`
keeps them.

### An export is a redistribution

Reading rows out of Postgres by hand, with DuckDB or anything else, loses
the rights information every other path in the kit enforces, and the copy
that leaves the database is the copy nobody re-checks. So the command takes
the same kind of license allowlist retrieval does, and applies it
fail-closed:

```bash
sci-rag corpus export export/ --license public --license open_commercial
```

`unknown` is excluded unless you name it, exactly as in retrieval. The graph
needs a stricter rule than the rows, because it aggregates: an entity's
description is written from evidence across every document it was extracted
from, so **an entity survives a scope only when every one of those documents
did**, and a relationship survives only when its own document did and both
its endpoints survived. An entity carrying no document attribution cannot be
checked, so a scoped export drops it.

Communities are never exported. A community summary aggregates across
documents with no per-document attribution to filter on, which is the same
reason the community retrieval layer disables itself under any scope.

### It is not a restore path

Vectors round-trip as arrays and the full-text columns get rebuilt on
ingest, so restores always go through `pg_restore` or Cloud SQL backups.
In Parquet, `documents.extra` is written as a JSON string rather than a
struct, because its keys vary per document and an inferred struct schema
would change with the corpus.

## Retrieval latency

```bash
sci-rag profile                       # interactive, deep, and auto over the seed questions
sci-rag profile --runs 10             # more replays, tighter percentiles
sci-rag profile --json                # machine-readable, for tracking over time
```

Nothing new is instrumented: every request already records a duration per
stage, and this replays the seed questions and aggregates those traces into
p50/p95 per stage, per profile, plus a one-line verdict naming the slowest
stage and what `auto` routed to.

Two things about the numbers are easy to misread, so the command says both out
loud rather than leaving them to you:

* **The stage column does not sum to the request time.** Candidate generators
  run concurrently, so a request is roughly as slow as its slowest stage, not
  as slow as their total. Wall-clock is measured separately and shown in each
  table's title.
* **The query-embedding cache is off while profiling.** Interactive requests
  normally cache query embeddings in process memory, so replaying one question
  ten times would measure the cache on runs 2 through 10 and report a p50 no
  real user ever sees. Every run is cold, which makes the profiles comparable
  and slightly pessimistic about a warm interactive path.

A stage that was switched off is not a failure. `interactive` disables graph,
community, and HyDE by definition, and an unconfigured reranker is a choice, so
those show in the status column but never as a degradation. The warning line is
reserved for stages that ran and did not succeed, because a stage that timed
out is fast for the wrong reason.

This measures speed, not quality. `docs/benchmarks.md` is where a layer earns
its place; the profiler only tells you what it costs.

## The habits that matter

1. Snapshot before and after every bulk change (ingest campaign,
   delete, reindex); the digest diff is your receipt.
2. Back up before schema migrations.
3. Run the restore drill when you set the project up, not during the
   incident.
4. `sci-rag doctor` after every restore.

<div class="srag-checkpoint" markdown>
**Checkpoint: the restore actually works**

You have run the drill at least once: dump, restore into a scratch database,
`sci-rag doctor` clean, and a corpus digest that matches the snapshot you took
before the dump. A backup you have never restored is a hypothesis.
</div>

## Next steps

- Re-embed after changing a model or a dimension: [Configuration](configuration.md)
- Understand what a snapshot pins, and why a citation needs one: [Evidence and rights](evidence-and-rights.md)
- Run the same service on managed infrastructure: [Deploy on Google Cloud](deploy-gcp.md)
