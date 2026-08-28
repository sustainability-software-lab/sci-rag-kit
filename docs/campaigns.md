---
title: Corpus campaigns
description: Discover a resumable DOI list, resolve explicit open-access rights, download verified PDFs, and write an ingestible corpus manifest.
---

# Corpus campaigns

A campaign turns a research topic or a seed DOI file into a reproducible
list of scientific works. Discovery is deliberately separate from ingestion:
you can inspect the candidates and resume network work before any document is
added to the corpus.

## Discover from a topic

Identify every API request with a monitored contact address:

```bash
uv run sci-rag campaign discover \
  --topic "rice straw valorization" \
  --name rice-straw \
  --mailto you@example.org \
  --max-results 100
```

Topic discovery searches OpenAlex and follows cursor pagination. Casual
keyless use is supported. For a larger API budget, set `OPENALEX_API_KEY` in
the environment; the key is never printed or written to campaign state.

## Discover from DOI seeds

Put one bare DOI, DOI URL, or `doi:` value on each line. Blank lines and lines
beginning with `#` are ignored.

```text
10.7717/peerj.4375
https://doi.org/10.1038/s41586-020-2649-2
```

Then run:

```bash
uv run sci-rag campaign discover \
  --doi-file seed-dois.txt \
  --name seed-review \
  --mailto you@example.org
```

DOI-file discovery normalizes and deduplicates the values, then retrieves
bibliographic metadata from Crossref. Invalid lines and malformed upstream
records are counted in the report instead of disappearing silently.

## Resume behavior

The default state path is `data/campaigns/<name>/state.jsonl`. Each completed
DOI step is appended and flushed to disk. Repeating the command skips DOI
records already present in state. If a process dies during the final write,
the next run ignores only the truncated tail and safely continues appending.

OpenAlex and Crossref calls are rate limited and identify the contact address
in both the query and User-Agent. HTTP 429 and server errors are retried with
bounded backoff. Exhausted retries fail visibly; they never become an empty
success report.

Discovery metadata is not proof that a document may be redistributed. Resolve
rights without downloading first:

```bash
uv run sci-rag campaign build \
  --topic "rice straw valorization" \
  --name rice-straw \
  --mailto you@example.org \
  --max-results 20 \
  --dry-run
```

The dry run queries Unpaywall for each DOI, prints direct-PDF counts and the
license-class distribution, and writes only resumable state. It does not
create `pdfs/` or `corpus.jsonl`.

## Fail-closed rights mapping

Availability and redistribution rights are different signals. A work marked
green or gold by Unpaywall is not assigned an open license class unless its
selected location also carries an explicit recognized license:

| Explicit location license | Corpus class |
| --- | --- |
| CC0 or public-domain mark | `public` |
| CC BY family | `open_commercial` |
| CC BY-NC family | `open_noncommercial` |
| Missing, `implied-oa`, publisher-specific, or unrecognized | `unknown` |

The mapping never infers a license from `oa_status`, a reachable URL, or a PDF
response. `unknown` is the intentional safe result when rights are unclear.

## Download and ingest

After reviewing the dry-run distribution, repeat the command without
`--dry-run`. The builder fetches only Unpaywall's direct `url_for_pdf` for a
record marked open access. It never visits a landing page to scrape through a
paywall.

Each response must declare `application/pdf`, stay within `--max-pdf-mb`, and
begin with a PDF signature. Files are written through a temporary path and
renamed only after validation. Verified existing files are reused after an
interruption instead of downloaded again.

Successful downloads produce `data/campaigns/<name>/corpus.jsonl`. It is the
same format consumed by:

```bash
uv run sci-rag ingest --manifest data/campaigns/rice-straw/corpus.jsonl
```

Every manifest row retains the normalized DOI, bibliographic metadata,
fail-closed `license_class`, and the exact Unpaywall license signal in
`license_source`.

## Screen a discovered campaign

Write the review protocol as plain text. State the inclusion and exclusion
criteria precisely enough that another reviewer could apply them without
outside context:

```text
Include field studies of rice-straw conversion with a measured material yield.
Exclude reviews, simulations without experimental validation, and studies of
other feedstocks.
```

Screen the abstracts already retained in campaign state:

```bash
uv run sci-rag campaign screen \
  --name rice-straw \
  --criteria-file screening-criteria.txt \
  --confidence-threshold 0.8
```

The model receives abstracts in bounded batches and must return one strict
`include` or `exclude` decision, confidence, and reason per work. The command
does not trust that output blindly:

* confidence below the threshold becomes `review`;
* a missing abstract becomes `review` without a model call;
* malformed JSON, missing rows, duplicate indexes, and provider failures make
  the affected batch `review`;
* no failure path silently excludes a work.

Decisions append to `state.jsonl`. The current protocol, its SHA-256 digest,
the confidence floor, every per-work reason, failure counts, and the current
PRISMA-aligned totals are written to `screening-report.json`. Repeating the
same protocol resumes without calling the model again. Changing the criteria
or confidence floor starts a new set of decisions while preserving the old
append-only history.

The screening report begins at the deduplicated campaign-state boundary.
`identified`, `screened`, and the sum of `included`, `excluded`, and
`awaiting_review` therefore reconcile against the unique discovered works.
Upstream duplicates were already removed and reported by `campaign discover`,
so `duplicates_removed` is zero at this boundary. Exclusions also include a
reason breakdown rather than only an aggregate count.

## Review uncertain rows

Walk the queue interactively:

```bash
uv run sci-rag campaign review --name rice-straw
```

For each row, choose `include`, `exclude`, or `skip`, then record a reason.
Human decisions append after the model suggestion instead of overwriting it,
and the report is regenerated from the latest decision under that protocol.
Skipping leaves the row in `awaiting_review`, so the totals continue to
reconcile without pretending the campaign is complete.
