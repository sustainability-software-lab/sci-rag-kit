# Benchmarks

Measured results on the shipped demo corpus, regenerated with one
command. This page exists to prove the evaluation harness end to
end and to publish honest numbers for THIS template on ITS demo
corpus; it makes no state-of-the-art claim and does not compare
against other systems (see docs/choosing-sci-rag-kit.md for the
honest comparison on axes other than benchmark scores).

## What was measured

- Corpus: 5 documents, 34 chunks, 94 entities, 107 relationships, 15 communities (the synthetic agricultural-residue demo corpus shipped in `data/demo/`)
- Corpus snapshot: `benchmark-20260828-034547-pre-resolution` (see `data/snapshots/`; the digest pins the exact document set)
- Embedding: `gemini-embedding-001@1536`; answer `google:gemini-2.5-flash`; judge `anthropic:claude-haiku-4-5`
- Code: commit `d815b70`
- Rendered: 2026-08-28

## Retrieval ablations

Cells are mean [95% bootstrap CI], resampled per question. The
demo corpus has single-digit questions, so intervals are wide by
construction: treat differences whose intervals overlap heavily as
noise, and read the table for the qualitative story (which layers
earn their keep) rather than decimal places. On a small sample
like this, that qualitative story is the only defensible claim.

| Config | hit@5 | hit@10 | MRR | nDCG@10 | n |
|--------|---:|---:|---:|---:|---:|
| full_deep | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.94 [0.83, 1.00] | 0.94 [0.87, 0.99] | 9 |
| interactive | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.96 [0.91, 1.00] | 9 |
| vector_only | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.96 [0.91, 1.00] | 9 |
| keyword_only | 0.33 [0.00, 0.67] | 0.33 [0.00, 0.67] | 0.33 [0.00, 0.67] | 0.33 [0.00, 0.67] | 9 |
| no_graph | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.97 [0.93, 1.00] | 9 |
| confidence_weighted | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.93 [0.78, 1.00] | 0.91 [0.80, 0.98] | 9 |
| with_citations | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.94 [0.83, 1.00] | 0.93 [0.86, 0.99] | 9 |
| no_hyde | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.96 [0.91, 0.99] | 9 |
| no_community | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.94 [0.83, 1.00] | 0.92 [0.87, 0.97] | 9 |
| with_rerank | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.97 [0.95, 0.99] | 9 |
| no_rerank | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.94 [0.90, 0.98] | 9 |
| auto_routed | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.96 [0.91, 0.99] | 9 |
| no_retracted | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.94 [0.83, 1.00] | 0.92 [0.83, 0.98] | 9 |

How to read it:

- `full_deep` vs the `*_only` rows shows what fusion buys over any
  single layer.
- `no_graph` / `no_hyde` / `no_community` vs `full_deep` shows each
  layer's marginal contribution on this corpus.
- `with_rerank` vs `no_rerank` is the paired evidence the reranker
  must show before `retrieval.reranker.enabled: true` is justified.
- `auto_routed` vs `full_deep` and `interactive` is the evidence for
  (or against) making adaptive routing a default. Until it clearly
  matches `full_deep` at lower cost, `auto` stays opt-in.
- `confidence_weighted` isolates confidence-aware graph ranking. Its
  interval overlaps the full condition, so this run does not justify a default.
- The shipped demo manifest has no cached DOI reference lists, so citation
  ingestion produced zero document edges. Treat `with_citations` as an
  unexercised control. Small movement from independent real-model retrieval
  calls is not evidence for or against citation traversal.
- `no_retracted` should be exactly neutral because the synthetic demo
  contains no known retracted document. Any apparent gain would be suspect.

## Entity-resolution condition

Entity resolution changes persisted corpus state, so it is shown separately
from same-state layer ablations. Because natural model extraction may have no
duplicates, this pair starts after inserting one explicitly labeled exact-alias
control entity. The resolver must create an audit row; unchanged state cannot be
relabeled as resolved.

| Condition | hit@5 | hit@10 | MRR | nDCG@10 | n |
|---|---:|---:|---:|---:|---:|
| full_deep before | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.94 [0.89, 0.98] | 9 |
| resolved_entities | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.94 [0.83, 1.00] | 0.91 [0.84, 0.97] | 9 |

Paired n=9; deltas are resolved minus pre-resolution:

| Metric | Delta [95% CI] | p |
|---|---:|---:|
| hit@5 | +0.000 [+0.000, +0.000] | 1.000 |
| hit@10 | +0.000 [+0.000, +0.000] | 1.000 |
| MRR | -0.056 [-0.167, +0.000] | 0.740 |
| nDCG@10 | -0.023 [-0.059, +0.004] | 0.141 |

The controlled merge preserved hit@5 and hit@10. Every paired interval includes zero, so this small run establishes neither a retrieval gain nor a degradation.

Control snapshot: `benchmark-20260828-034547-resolution-control`. Post-resolution snapshot:
`benchmark-20260828-034547-resolved`.
Both resolution reports were measured at commit `19a058f`.

## Judged answers, uncompressed condition (blind two-pass judge)

| Dimension | Mean [95% CI] |
|-----------|--------------:|
| groundedness | 2.00 [2.00, 2.00] |
| citation_accuracy | 2.00 [2.00, 2.00] |
| completeness | 1.90 [1.70, 2.00] |
| correctness | 2.00 [2.00, 2.00] |
| graded / total | 10 / 10 |

The grounding judge never sees the reference answer; correctness
is graded in a separate reference-only pass (docs/evaluation.md).

## Snippet-compression condition

Both rows share one corpus fingerprint, snapshot, commit, question set, answer
model, and judge. The grounding judge sees the exact compressed or
fallback source text shown to the answer model.

| Condition | groundedness | citation accuracy | completeness | correctness | median prompt tokens | chunk fallbacks |
|---|---:|---:|---:|---:|---:|---:|
| uncompressed | 2.00 [2.00, 2.00] | 2.00 [2.00, 2.00] | 1.90 [1.70, 2.00] | 2.00 [2.00, 2.00] | 1346.0 | 0 |
| compressed | 2.00 [2.00, 2.00] | 2.00 [2.00, 2.00] | 1.90 [1.70, 2.00] | 2.00 [2.00, 2.00] | 360.0 | 0 |

Paired n=10; deltas are compressed minus uncompressed:

| Metric | Delta [95% CI] | p |
|---|---:|---:|
| groundedness | +0.000 [+0.000, +0.000] | 1.000 |
| citation_accuracy | +0.000 [+0.000, +0.000] | 1.000 |
| completeness | +0.000 [-0.300, +0.300] | 1.000 |
| correctness | +0.000 [+0.000, +0.000] | 1.000 |
| prompt_tokens | -973.300 [-1044.105, -906.080] | 0.000 |

The paired gate passed: every quality interval includes zero and the prompt-token interval is below zero. The shipped demo enables compression.

## Judge calibration (human labels vs judge)

Cohen's kappa between independent human labels
(`domain/eval_calibration_labels.jsonl`, a NON-EXPERT seed set)
and the judge's scores on the same answers:

| Dimension | kappa | exact agreement | n |
|-----------|------:|----------------:|--:|
| groundedness | 1.00 | 1.00 | 10 |
| citation_accuracy | 1.00 | 1.00 | 10 |
| completeness | 0.00 | 0.90 | 10 |
| correctness | 1.00 | 1.00 | 10 |

Kappa is reported as measured, never asserted as a target. A
kappa of 0 with high exact agreement means one rater was
constant (kappa cannot credit agreement it attributes to
chance); the fix is a seed set with more score variance, not a
different formula. Expert labels supersede this seed set.

## Reproduce it

```bash
make benchmark
```

Prerequisites: Docker (for the pgvector Postgres), uv, Google
credentials in `.env` (`SCI_RAG_GOOGLE_API_KEY` or
`SCI_RAG_GCP_PROJECT`; see `.env.example`), and database-create permission
for the configured PostgreSQL role. Each run creates and preserves a fresh
isolated Postgres database so entity-resolution state from an earlier run
cannot be mislabeled as a pre-resolution baseline. The target ingests the
demo corpus with real embeddings, builds the graph, snapshots the
corpus, runs the full retrieval ablation, audited entity-resolution
condition, and both judged-answer compression conditions, then
re-renders this page from the report JSONs. Without
credentials the eval commands stop with a clear message; nothing
on this page is reachable offline, by design: published numbers
come from real models or not at all.
