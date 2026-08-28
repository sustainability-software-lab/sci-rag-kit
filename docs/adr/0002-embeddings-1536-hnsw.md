# ADR 0002: 1536-dimension embeddings, so HNSW indexing actually works

**Status:** accepted

## Context

Modern embedding models emit up to 3072 dimensions, and bigger sounds
better. But pgvector's HNSW index tops out at 2000. Give it a
3072-dimension column and it quietly falls back to exact scans, where
every vector query reads every row. At ten thousand chunks that is fine.
Past that it hurts, and it is the kind of slowdown nobody notices until
the corpus has already grown.

Models trained with Matryoshka representation learning, the default
`gemini-embedding-001` among them, are designed to be truncated: the
first N dimensions carry most of the signal, at a small and published
cost in quality.

## Decision

Default to 1536 dimensions, requested from the model via
`output_dimensionality`, with two guardrails:

* Re-normalize every truncated vector to unit length before storing it.
  Truncation breaks the unit norm that cosine ranking assumes.
* Check the configured dimension twice. The provider asserts it on every
  response and the database column enforces it on every insert, so a
  model or configuration mismatch fails at the source.

`SCI_RAG_EMBEDDING_DIM` sets the dimension, and a migration bakes it into
the schema. Changing it later takes a migration and a full re-embed. The
`embedding_version` stamp on every chunk is what makes the second half
tractable: the embedder re-runs only the chunks whose stamp no longer
matches.

## Consequences

* Vector search stays indexed as the corpus grows. The demo's ~2 second
  vector stage is connection and API latency, not scan time.
* Full 3072 dimensions would retrieve slightly better. If that ever
  matters for a corpus, measure the gap with the ablation harness before
  paying the exact-scan price.
