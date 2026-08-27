# Benchmarks

Measured results on the shipped demo corpus, regenerated with one
command. This page exists to prove the evaluation harness end to
end and to publish honest numbers for THIS template on ITS demo
corpus; it makes no state-of-the-art claim and does not compare
against other systems (see docs/choosing-sci-rag-kit.md for the
honest comparison on axes other than benchmark scores).

## What was measured

- Corpus: 5 documents, 34 chunks, 89 entities, 91 relationships, 12 communities (the synthetic agricultural-residue demo corpus shipped in `data/demo/`)
- Corpus snapshot: `benchmark-20260827-163251` (see `data/snapshots/`; the digest pins the exact document set)
- Embedding: `gemini-embedding-001@1536`; generation and judging: `gemini-2.5-flash`
- Code: commit `1138d88`
- Rendered: 2026-08-27

## Retrieval ablations

Cells are mean [95% bootstrap CI], resampled per question. The
demo corpus has single-digit questions, so intervals are wide by
construction: treat differences whose intervals overlap heavily as
noise, and read the table for the qualitative story (which layers
earn their keep) rather than decimal places. On a small sample
like this, that qualitative story is the only defensible claim.

| Config | hit@5 | hit@10 | MRR | nDCG@10 | n |
|--------|---:|---:|---:|---:|---:|
| full_deep | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.95 [0.90, 0.98] | 9 |
| interactive | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.96 [0.91, 1.00] | 9 |
| vector_only | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.96 [0.91, 1.00] | 9 |
| keyword_only | 0.33 [0.00, 0.67] | 0.33 [0.00, 0.67] | 0.33 [0.00, 0.67] | 0.33 [0.00, 0.67] | 9 |
| no_graph | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.95 [0.90, 0.99] | 9 |
| no_hyde | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.94 [0.90, 0.98] | 9 |
| no_community | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.97 [0.95, 1.00] | 9 |
| with_rerank | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.96 [0.93, 0.99] | 9 |
| no_rerank | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.94 [0.83, 1.00] | 0.93 [0.86, 0.98] | 9 |
| auto_routed | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 1.00 [1.00, 1.00] | 0.97 [0.93, 0.99] | 9 |

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

## Judged answers (blind two-pass judge)

| Dimension | Mean [95% CI] |
|-----------|--------------:|
| groundedness | 2.00 [2.00, 2.00] |
| citation_accuracy | 2.00 [2.00, 2.00] |
| completeness | 2.00 [2.00, 2.00] |
| correctness | 1.40 [0.90, 1.80] |
| graded / total | 10 / 10 |

The grounding judge never sees the reference answer; correctness
is graded in a separate reference-only pass (docs/evaluation.md).

## Judge calibration (human labels vs judge)

Cohen's kappa between independent human labels
(`domain/eval_calibration_labels.jsonl`, a NON-EXPERT seed set)
and the judge's scores on the same answers:

| Dimension | kappa | exact agreement | n |
|-----------|------:|----------------:|--:|
| groundedness | 1.00 | 1.00 | 10 |
| citation_accuracy | 1.00 | 1.00 | 10 |
| completeness | 1.00 | 1.00 | 10 |
| correctness | 0.00 | 0.60 | 10 |

Kappa is reported as measured, never asserted as a target. A
kappa of 0 with high exact agreement means one rater was
constant (kappa cannot credit agreement it attributes to
chance); the fix is a seed set with more score variance, not a
different formula. Expert labels supersede this seed set.

## Reproduce it

```bash
make benchmark
```

Prerequisites: Docker (for the pgvector Postgres), uv, and Google
credentials in `.env` (`SCI_RAG_GOOGLE_API_KEY` or
`SCI_RAG_GCP_PROJECT`; see `.env.example`). The target ingests the
demo corpus with real embeddings, builds the graph, snapshots the
corpus, runs the full retrieval ablation plus the judged answers
eval, and re-renders this page from the report JSONs. Without
credentials the eval commands stop with a clear message; nothing
on this page is reachable offline, by design: published numbers
come from real models or not at all.
