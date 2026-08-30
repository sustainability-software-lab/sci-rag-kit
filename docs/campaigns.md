---
title: Run a corpus campaign
description: Discover a resumable DOI list, resolve explicit open-access rights, download verified PDFs, and write an ingestible corpus manifest.
---

# Run a corpus campaign

A campaign turns a research topic or a seed DOI file into a reproducible list
of scientific works, with an explicit rights answer attached to every one.
Discovery stays separate from ingestion on purpose, so you can inspect the
candidates and resume interrupted network work before anything lands in the
corpus.

<div class="srag-meta-strip">
  <div><strong>You'll build</strong>A screened, rights-resolved corpus manifest</div>
  <div><strong>You'll need</strong>A topic or a DOI list, and a contact email</div>
  <div><strong>Time</strong>Minutes to run, longer to review</div>
  <div><strong>Credentials</strong>Optional, for the screening model only</div>
  <div><strong>Tested with</strong>v0.4</div>
</div>

## Before you start

| Requirement | Why | Check |
|---|---|---|
| A working database | The manifest is only useful once you ingest it | `uv run sci-rag doctor` |
| A contact email you monitor | OpenAlex, Crossref, and Unpaywall all want one, and rate-limit anonymous callers hard | |
| A topic phrase or a file of DOIs | The two ways to start a campaign | |
| Network access | Every step here talks to an external index | |

Campaigns never decide rights for you. Discovery produces candidates and an
explicit open-access signal; anything unestablished stays `unknown`, which
retrieval treats as unsafe.

## Discover from a topic

Identify every API request with a monitored contact address:

```bash
uv run sci-rag campaign discover \
  --topic "rice straw valorization" \
  --name rice-straw \
  --mailto you@example.org \
  --max-results 100
```

Topic discovery searches OpenAlex and follows cursor pagination. Casual use
works without a key. For a larger API budget, set `OPENALEX_API_KEY` in the
environment. The kit never prints that key and never writes it to campaign
state.

## Discover from DOI seeds

Put one bare DOI, DOI URL, or `doi:` value on each line. The reader skips
blank lines and lines beginning with `#`.

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
bibliographic metadata from Crossref. The report counts invalid lines and
malformed upstream records, so none of them disappears silently.

## Resume behavior

The default state path is `data/campaigns/<name>/state.jsonl`. The run appends
each completed DOI step and flushes it to disk. Repeating the command skips
DOI records already present in state. If a process dies during the final write,
the next run ignores only the truncated tail and safely continues appending.

OpenAlex and Crossref calls are rate limited and identify the contact address
in both the query and User-Agent. The client retries HTTP 429 and server
errors with bounded backoff. Exhausted retries fail visibly; they never become an empty
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

`--max-results` bounds the work this invocation does, not only what discovery
adds. The campaign above retains 100 candidates, so `--max-results 20` resolves
the first 20 of them and leaves the rest untouched, in dry run and in download
mode alike. The report says both numbers, `retained` and `candidates`, so a
bounded trial cannot read as a full run. Campaign state is append-only and the
bound takes a prefix of it, so a retry works on the same 20 rather than
sampling a new set. Pass `--all-candidates` when you want every retained
candidate regardless of the maximum.

## Fail-closed rights mapping

Availability and redistribution rights are different signals. Unpaywall
marking a work green or gold is not enough on its own. A work earns an open
license class only when its selected location also carries an explicit,
recognized license:

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
begin with a PDF signature. The builder writes files through a temporary path
and renames them only after validation. After an interruption it reuses files
it has already verified, so a resumed run downloads nothing twice.

Successful downloads produce `data/campaigns/<name>/corpus.jsonl`, in the same
format `sci-rag ingest` reads:

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

Decisions append to `state.jsonl`. `screening-report.json` records the current
protocol, its SHA-256 digest, the confidence floor, every per-work reason,
failure counts, and the current PRISMA-aligned totals. PRISMA is the
Preferred Reporting Items for Systematic Reviews and Meta-Analyses. It is
the reporting standard systematic reviews are held to, so aligning with it
means the counts are the ones a reviewer expects. Repeating the same
protocol resumes without calling the model again. Changing the criteria
or confidence floor starts a new set of decisions while preserving the old
append-only history.

The screening report begins at the deduplicated campaign-state boundary.
`identified`, `screened`, and the sum of `included`, `excluded`, and
`awaiting_review` therefore reconcile against the unique discovered works.
`campaign discover` already removed and reported the upstream duplicates, so
`duplicates_removed` is zero at this boundary. Exclusions also include a
reason breakdown rather than only an aggregate count.

## Review uncertain rows

Walk the queue interactively:

```bash
uv run sci-rag campaign review --name rice-straw
```

For each row, choose `include`, `exclude`, or `skip`, then record a reason.
Human decisions append after the model suggestion instead of overwriting it,
and the report regenerates from the latest decision under that protocol.
Skipping leaves the row in `awaiting_review`, so the totals continue to
reconcile without pretending the campaign is complete.

<div class="srag-checkpoint" markdown>
**Checkpoint: every row has a decision or a reason**

`sci-rag campaign review --name rice-straw` ends by printing the
PRISMA-aligned counts and the path to
`data/campaigns/rice-straw/screening-report.json`, which it rewrites from the
latest decisions. In that table `included` plus `excluded` plus
`awaiting review` equals `screened`. No row is missing, and no row is included
without a rights answer you can point at.
</div>

## Next steps

- Ingest the manifest this produced: [Bring your own domain](bring-your-own-domain.md#step-5-ingest-and-build)
- Understand what a license class does to retrieval: [Evidence and rights](evidence-and-rights.md)
- Enrich the DOIs and check for retractions: [Operate a live corpus](operations.md)
