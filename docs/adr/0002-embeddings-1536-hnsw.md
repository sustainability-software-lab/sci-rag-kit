# ADR 0002: 1536-dimension embeddings, so HNSW indexing actually works

**Status:** accepted

## Context

Modern embedding models emit up to 3072 dimensions, and bigger sounds
better. But pgvector's HNSW index supports at most 2000 dimensions, so a
3072-dimension column silently falls back to exact scans: every vector
query reads every row. That is fine at ten thousand chunks and painful
after that, and it is the kind of degradation nobody notices until the
corpus has grown.

Embedding models trained with Matryoshka representation learning
(including the default `gemini-embedding-001`) are designed to be
truncated: the first N dimensions carry most of the signal, at a small,
published quality cost.

## Decision

Default to 1536 dimensions, requested from the model via
`output_dimensionality`, with two guardrails:

* Truncated vectors are re-normalized to unit length before storage
  (truncation breaks the unit norm that cosine ranking assumes).
* The provider asserts the configured dimension on every response, and
  the database column enforces it on every insert, so a model or
  configuration mismatch fails at the source.

The dimension is configuration (`SCI_RAG_EMBEDDING_DIM`), baked into the
schema at migration time; changing it is an explicit migration plus
re-embed, aided by the `embedding_version` stamp on every chunk.

## Consequences

* Vector search stays indexed as the corpus grows; the demo's ~2 second
  vector stage is connection and API latency, not scan time.
* A small retrieval-quality cost versus full 3072 dimensions; if that
  ever matters for a corpus, the honest path is to measure it with the
  ablation harness before paying the exact-scan price.
