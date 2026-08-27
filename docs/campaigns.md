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

Discovery metadata is not proof that a document may be redistributed. The
campaign build step resolves explicit open-access license signals, downloads
only legal PDF locations, and fails closed when rights are unknown.
