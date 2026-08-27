# Changelog

Notable changes to sci-rag-kit. The format follows
[Keep a Changelog](https://keepachangelog.com/); versions follow
[Semantic Versioning](https://semver.org/) once past 1.0.

## [0.2.0] - 2026-08-27

The "Credibility" release: the gaps between what the methodology
document promised and what the code did are closed, and the launch
package (roadmap, governance, comparison, benchmarks) is in place.

### Added

- Post-fusion reranker stage: `Reranker` protocol with an LLM adapter
  (default, zero new dependencies) and a local cross-encoder adapter
  behind the new `rerank` extra; per-request `include_rerank`
  overrides on the retriever and `/v1/query`; honest `rerank` stage
  traces with fused-order fallback on any failure. Off by default
  pending ablation evidence.
- Eval statistics: bootstrap 95% confidence intervals on every
  reported mean (question-level resampling, stdlib only,
  deterministic), small-sample warnings below 10 questions, paired
  bootstrap comparisons, and nDCG@10 alongside hit@k/MRR.
- `sci-rag eval diff`: per-question rank moves (improved, regressed,
  appeared, disappeared) and paired metric deltas with significance
  between any two eval runs; answers-mode dimension diffs.
- `sci-rag eval calibrate`: Cohen's kappa per judge dimension against
  human labels, agreement matrices, calibration sections appended to
  answers reports; ships a non-expert seed label set for the demo
  corpus (`domain/eval_calibration_labels.jsonl`).
- `sci-rag embed reindex`: find and re-embed rows stamped by retired
  embedder versions, batch-committed and idempotent; refuses
  cross-dimension reindexes; community summaries now carry embedding
  version stamps (migration 0002).
- `sci-rag corpus delete` + `sci-rag graph gc`: transactional document
  deletion that scrubs graph evidence arrays, drops evidenced
  relationships and affected communities, and a garbage-collection
  sweep for evidence-less entities and dangling pointers; regression
  test proves deleted content unreachable through every retrieval
  layer.
- `sci-rag corpus snapshot`: named, immutable corpus fingerprints
  (counts, per-document content hashes, embedding versions, git
  commit, corpus digest); eval runs record the snapshot name via
  `--snapshot`.
- Adaptive routing: `--profile auto` resolves per query through
  transparent heuristics (multi-hop, overview, lookup cues) with
  reasons, an optional ambiguity-only LLM fallback, a router trace,
  and `--explain-routing`; default profile unchanged pending the
  published ablation.
- `docs/benchmarks.md`: measured demo-corpus results (all ablation
  configs including rerank and routing, judged answers, judge
  calibration) with confidence intervals, corpus snapshot, commit and
  model ids, reproducible via `make benchmark`.
- `docs/operations.md`: backup/restore runbook (pg_dump, Cloud SQL,
  restore drill, Parquet export note).
- Launch package: `docs/ROADMAP.md` (waves 2-3, UW SSEC collaboration
  seams, BioCirV flagship, launch-gated decisions),
  `docs/VERSIONING.md` (0.x rules, 1.0 criteria),
  `docs/GOVERNANCE.md`, `docs/choosing-sci-rag-kit.md` (honest
  comparison), `ADOPTERS.md`, and a runnable
  `examples/bring_your_own_domain.ipynb` (verified offline).
- Doctor: embedding-version staleness and graph-hygiene checks.

### Changed

- Retrieval eval reports state n and a 95% CI everywhere a mean
  appears; retrieval tables gained an nDCG@10 column.
- `/v1/query` accepts `profile: "auto"` and `include_rerank`.

## [0.1.0a0] - 2026-08-26

First working release of the template.

### Added

- Ingestion: Docling/pypdf/Markdown parsing, structure-aware chunking
  (section breadcrumbs, intact tables, 800/150 token defaults),
  content-hash deduplication, per-document license classes, JSONL corpus
  manifests.
- Storage: single-Postgres schema (Alembic) with pgvector HNSW and
  full-text GIN indexes; embedding version stamping.
- Embeddings: Google `gemini-embedding-001` at 1536 dimensions
  (Matryoshka, re-normalized) via AI Studio key or Vertex AI; a
  deterministic offline hash embedder for tests and dry runs.
- Knowledge graph: ontology-constrained LLM extraction with evidence
  provenance, incremental stamping, deterministic label-propagation
  communities with LLM summaries.
- Retrieval: five layers (vector, keyword, graph traversal, community
  summaries, HyDE) with weighted RRF fusion, interactive/deep profiles,
  per-stage timeouts and traces, fail-closed license/source/exclusion
  scoping inside every layer.
- Answering: numbered inline citations, refusal when nothing is in
  scope, streaming events.
- Evaluation: seed questions, hit@k/MRR with seven ablation configs, a
  two-pass blind judge (grounding never sees the reference answer),
  fingerprint-stamped JSON and Markdown reports, a CI smoke eval.
- Serving: FastAPI `/v1` (SSE answers, RFC 9457 errors, request ids,
  scoped API keys with rate limits, BYO LLM key) and an MCP server with
  seven tools and two resources, over streamable HTTP and stdio.
- Operations: `sci-rag doctor`, docker-compose Postgres, Dockerfile,
  validated Terraform for Cloud SQL + Cloud Run, GitHub Actions CI.
- Template ergonomics: `domain/` specialization surface,
  `scripts/init_domain.py`, offline synthetic demo corpus with seed
  questions and committed real-model eval reports, full documentation
  suite with ADRs.
