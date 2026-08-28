# Operations: snapshots, backup, restore

Everything the kit knows lives in one Postgres database, which keeps the
operational discipline short. Snapshot what the corpus **is**, back up what
the database **holds**, and rehearse the restore before you need it.

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

## Analytical export (optional)

For sharing data outside Postgres (or belt-and-suspenders archival), a
Parquet export of the four core tables works well:

```bash
# DuckDB reads Postgres directly and writes Parquet:
duckdb -c "
  INSTALL postgres; LOAD postgres;
  ATTACH 'postgresql://sci_rag:sci_rag@localhost:5433/sci_rag' AS db (TYPE postgres);
  COPY db.documents TO 'export/documents.parquet';
  COPY db.chunks TO 'export/chunks.parquet';
  COPY db.kg_entities TO 'export/kg_entities.parquet';
  COPY db.kg_relationships TO 'export/kg_relationships.parquet';
"
```

Parquet export is a convenience for analysis, not a restore path. Vectors
round-trip as text and the full-text columns get rebuilt, so restores
always go through `pg_restore` or Cloud SQL backups.

## The habits that matter

1. Snapshot before and after every bulk change (ingest campaign,
   delete, reindex); the digest diff is your receipt.
2. Back up before schema migrations.
3. Run the restore drill when you set the project up, not during the
   incident.
4. `sci-rag doctor` after every restore.
