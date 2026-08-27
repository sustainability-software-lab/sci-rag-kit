# Changelog

Notable changes to sci-rag-kit. The format follows
[Keep a Changelog](https://keepachangelog.com/); versions follow
[Semantic Versioning](https://semver.org/) once past 1.0.

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
