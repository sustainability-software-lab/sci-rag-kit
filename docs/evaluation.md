# The evaluation guide

The harness is designed to make results hard to game, including by
accident: mechanical retrieval metrics against expert ground truth,
per-layer ablations that show what each component contributes, and a
judge whose prompts structurally separate grounding from correctness.
This page covers usage and the reasoning behind the design.

## The two commands

```bash
sci-rag eval retrieval --ablation   # did the right evidence come back, per layer?
sci-rag eval answers                # are the generated answers grounded, cited, correct?
```

Both read `domain/eval_seed_questions.jsonl`, print a summary table, and
write a JSON + Markdown report to `eval_results/`, stamped with a corpus
fingerprint (documents, chunks, graph size, embedding versions, latest
ingestion time) and the git commit. Keep the reports; a number without
its fingerprint is just a rumor.

Real example output from the shipped demo corpus:
[examples/demo-eval/retrieval-ablation.md](examples/demo-eval/retrieval-ablation.md)
and [examples/demo-eval/answers.md](examples/demo-eval/answers.md).

## Seed questions: your ground truth

One JSON object per line:

```jsonl
{"id": "biogas-yield-pretreated",
 "question": "What biogas yield does alkali-pretreated rice straw achieve per dry ton?",
 "reference_answer": "About 320 cubic meters per dry ton at roughly 54 percent methane.",
 "reference_titles": ["Anaerobic Digestion of Crop Residues: A Working Primer"],
 "evidence_phrases": ["alkali pretreated", "320"],
 "tags": ["conversion"]}
```

* **question**: exactly as a user would ask it, not exam-speak.
* **reference_answer**: what a correct answer must say. An expert should
  be willing to sign it.
* **reference_titles**: the documents that contain the answer.
* **evidence_phrases**: distinctive strings from the passages that
  answer it. Numbers with units are ideal; short generic strings (under
  three characters) are ignored on purpose.
* **tags**: your own labels, plus one special value: `unanswerable`
  marks an honesty probe (see below).

Writing advice: 10 great questions beat 100 vague ones; include one or
two multi-hop questions whose evidence spans documents; and grow the set
from real user questions, especially ones the system fumbled.

## Retrieval metrics, and how to read the ablation table

A retrieved item counts as **relevant** to a question if it comes from a
reference document or contains an evidence phrase (case and whitespace
normalized). From that: hit@5, hit@10, and MRR (mean reciprocal rank of
the first relevant item).

This is deliberately mechanical. Its job is regression detection and
layer comparison, not absolute truth; the judged answer eval is where
quality judgment lives. What it will never do is grade generated answer
text by substring matching; that famous shortcut ("the answer contains
'IRR', so it is grounded") measures nothing and this kit refuses to
implement it.

`--ablation` re-runs the questions under the registered configurations:
`full_deep`, `interactive`, `vector_only`, `keyword_only`, `no_graph`,
`confidence_weighted`, `with_citations`, `no_hyde`, `no_community`, the paired reranker rows,
`auto_routed`, and `no_retracted`. Entity resolution changes persisted corpus state, not
retrieval kwargs, so it is intentionally not a row in this same-state table.
Capture it as two named snapshots instead:

```bash
sci-rag eval retrieval --snapshot before-resolution
sci-rag graph resolve-entities --apply
sci-rag eval retrieval --condition resolved_entities --snapshot after-resolution
sci-rag eval diff BEFORE.json AFTER.json
```

The post-resolution command requires a durable merge audit row, preventing an
unchanged corpus from being mislabeled. Read every layer-ablation row against
`full_deep`:

* A layer earns its fusion weight when REMOVING it hurts. If `no_graph`
  equals `full_deep` on your corpus, your graph is not contributing yet;
  fix the ontology or the corpus before touching weights.
* `vector_only` versus `keyword_only` tells you how your users' phrasing
  relates to your documents' phrasing. On the demo corpus, keyword-only
  scores 0.33 where vector scores 1.00; that gap is the reason hybrid
  retrieval exists.
* Small corpora saturate: with five demo documents, most configs hit
  1.00 and only the differences matter. Expect real spread as the corpus
  grows.

## The judge, and why it is blind

Grading a generated answer happens in two independent passes:

**Pass 1, grounding (blind).** The judge sees the question, the answer,
and exactly the sources the assistant retrieved. It scores three
dimensions, 0 to 2 each: groundedness (claims supported by the sources),
citation accuracy (the bracketed numbers point at sources that really
support the adjacent claim), completeness (the relevant retrieved
material was used). It never sees the reference answer. A judge that
does will happily reward an answer for matching the reference even when
the cited sources say no such thing, which quietly converts your
grounding metric into a paraphrase detector.

**Pass 2, correctness (reference-based).** A separate call compares the
answer against the expert reference, without the sources, and scores
factual agreement 0 to 2. The reference is a floor, not a ceiling: extra
correct detail is never penalized.

Both passes run at temperature 0, scores are clamped to the rubric, and
a malformed judge response is recorded as a failure, never silently
coerced. The judge prompts live in `domain/prompts/judge_grounding.md`
and `judge_correctness.md`; if you edit them, keep the blindness rules
intact, and spot-check a handful of judged answers by hand afterward
(read the rationale strings in `report.json`; they are kept for exactly
this).

## Calibrating the judge

The judged-answers table is only as citable as the judge behind it, so
the kit ships calibration as a workflow you re-run, not a one-off study:

1. Run an answers eval (`sci-rag eval answers`) and open its
   `report.json` in `eval_results/`.
2. Have a human read each generated answer (and its sources) WITHOUT
   looking at the judge's scores, and record their own 0-2 scores per
   dimension, one JSON object per line:

   ```
   {"question_id": "rice-straw-ash", "groundedness": 2,
    "citation_accuracy": 2, "completeness": 1, "correctness": 2}
   ```

   `#` comment lines are allowed. Dimensions may be omitted per row.
3. Compare:

   ```bash
   uv run sci-rag eval calibrate --labels labels.jsonl --report eval_results/<run>/report.json
   ```

   You get Cohen's kappa per dimension, exact agreement, and the full
   3x3 agreement matrices. The section is appended to the run's
   `report.md` and stored as `calibration.json` next to it, so the kappa
   travels with the numbers it qualifies.

Report kappa as measured. The Landis-Koch adjective in the output
("moderate", "substantial", ...) is a standard reading aid, not a
target; a low kappa on a dimension is a real finding that the judge and
a human disagree there, and the agreement matrix shows how. Expect
unstable kappa below roughly 30 labeled answers; more labels, and labels
from a domain expert, make the number mean more.

The repo ships `domain/eval_calibration_labels.jsonl`: a seed label set
for the demo corpus, labeled by the kit's authors. It is marked
non-expert; it demonstrates the workflow and pins the format, and domain
expert labels (the BioCirV collaboration supplies them for the flagship
deployment) supersede it for any real claim about judge reliability.

## Honesty probes

Include at least one question your corpus cannot answer, tagged
`unanswerable`. Retrieval metrics skip it; the answer eval keeps it. A
healthy system responds "the corpus does not cover this" and the
grounding judge scores that honesty a 2. If your probe comes back with a
confident invented answer, stop tuning retrieval and fix your answer
prompt first.

## CI keeps the demo honest

`tests/integration/test_eval_smoke.py` runs the retrieval eval on the
shipped demo corpus with the offline embedder on every CI run, with
conservative thresholds (hit@10 at least 0.65). It exists to catch a
broken chunker, layer, or seed file before it ships, and it is the
pattern to copy to protect your own corpus with CI: freeze a
small fixture corpus, pin thresholds under your current numbers, and let
regressions fail loudly.

## The improvement loop

1. Establish the baseline: both eval commands, reports saved.
2. Change one thing (chunk size, a prompt, the ontology, a fusion
   weight).
3. Re-run, then let the diff tool do the comparison:

   ```bash
   uv run sci-rag eval diff eval_results/<baseline-run> eval_results/<new-run>
   ```

   It reports which questions moved (improved, regressed, appeared,
   disappeared) and whether each metric delta clears paired-bootstrap
   significance, so a lucky rank flip on one question cannot pass as an
   improvement.
4. Keep the change only if the numbers (and your reading of the judged
   answers) agree it helped.

When two people disagree about whether a change helped, the reports
settle it.
