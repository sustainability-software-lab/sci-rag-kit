---
title: Evaluate your pipeline
description: Run retrieval ablations and judged-answer evaluation, compare two reports, and calibrate the judge against human labels.
---

# Evaluate your pipeline

By the end of this page you can say, with evidence, whether a change to your
pipeline helped. The harness is built to make that hard to fake, including by
accident: mechanical retrieval metrics against expert ground truth, per-layer
ablations showing what each component contributes, and a judge whose prompts
structurally separate grounding from correctness.

<div class="srag-meta-strip">
  <div><strong>You'll build</strong>A reproducible before-and-after on your own corpus</div>
  <div><strong>You'll need</strong>An ingested corpus and seed questions</div>
  <div><strong>Time</strong>About 20 minutes for the first run</div>
  <div><strong>Credentials</strong>Required for judged answers</div>
  <div><strong>Tested with</strong>v0.4</div>
</div>

## Before you start

| Requirement | Why | Check |
|---|---|---|
| An ingested corpus | Every metric is computed against real chunks | `uv run sci-rag stats` |
| `domain/eval_seed_questions.jsonl`, reviewed | This file is the ground truth. Drafted rows still tagged `drafted` make every number provisional | `uv run sci-rag doctor` |
| A model credential | Retrieval metrics run offline; judged answers do not | `grep SCI_RAG_GOOGLE .env` |
| A corpus snapshot, for anything you will cite | A number without a corpus identity is not reproducible | `uv run sci-rag corpus snapshot` |

## The two commands

```bash
sci-rag eval retrieval --ablation   # did the right evidence come back, per layer?
sci-rag eval answers                # are the generated answers grounded, cited, correct?
```

Both read `domain/eval_seed_questions.jsonl`, print a summary table, and
write a JSON and Markdown report to `eval_results/`. Every report carries a
corpus fingerprint (documents, chunks, graph size, embedding versions,
latest ingestion time) and the git commit. Keep the reports; a number
without its fingerprint is just a rumor.

Real example output from the shipped demo corpus:
[examples/demo-eval/retrieval-ablation.md](examples/demo-eval/retrieval-ablation.md)
and [examples/demo-eval/answers.md](examples/demo-eval/answers.md).

## Seed questions: your ground truth

One JSON object per line:

```jsonl title="domain/eval_seed_questions.jsonl"
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
* **tags**: your own labels, plus two special values. `unanswerable`
  marks an honesty probe (see below), and `drafted` marks a question a
  model wrote that no expert has checked yet (see below).

Three pieces of writing advice. Ten great questions beat a hundred vague
ones. Include one or two multi-hop questions whose evidence spans
documents. And grow the set from real user questions, especially the ones
the system fumbled.

If typing them cold is the part you keep putting off,
[`sci-rag draft questions`](bring-your-own-domain.md#step-5-write-seed-questions-then-measure) writes a first pass
grounded in your own documents and verifies every quoted phrase against the
passage it claims to come from.

If you already have the questions, which is the better position to be in,
[`sci-rag draft seed-from-answers questions.txt`](bring-your-own-domain.md#step-5-write-seed-questions-then-measure) fills
in the rest. It answers each of your questions and proposes the reference
answer and evidence phrases from what that answer cited, keeping only phrases
that appear verbatim in both the answer and its source. Rows arrive tagged
`drafted` like any other draft, and the reference answers are the kit's own
words, so they are hypotheses until you have checked them.

## Drafted ground truth is provisional, and the report says so

A question tagged `drafted` came from a model. That tag is provenance, and
it travels into the reports: while any question carries it, both
`sci-rag eval retrieval` and `sci-rag eval answers` print a warning saying
how many of the questions behind the numbers are unreviewed, and the JSON
carries the same receipt.

The JSON block sits beside the corpus fingerprint:

```json
"ground_truth": {"drafted": 7, "reviewed": 3}
```

Read the question, check its evidence against the document it cites, then
delete the `drafted` tag. That deletion is the expert sign-off, and it is
the only thing that moves the counts. Nothing in the kit removes the tag
for you.

## Retrieval metrics, and how to read the ablation table

A retrieved item counts as **relevant** to a question if it comes from a
reference document or contains an evidence phrase (case and whitespace
normalized). From that: hit@5, hit@10, and MRR (mean reciprocal rank of
the first relevant item).

This is deliberately mechanical. Its job is regression detection and
layer comparison, not absolute truth; the judged answer eval is where
quality judgment lives. What it will never do is grade generated answer
text by substring matching. That famous shortcut, where "the answer
contains 'IRR', so it is grounded", measures nothing, and this kit refuses
to implement it.

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

* A layer earns its fusion weight when **removing** it hurts. If `no_graph`
  equals `full_deep` on your corpus, your graph is not contributing yet;
  fix the ontology or the corpus before touching weights.
* `vector_only` versus `keyword_only` tells you how your users' phrasing
  relates to your documents' phrasing. On the demo corpus, keyword-only
  scores 0.33 where vector scores 1.00; that gap is the reason hybrid
  retrieval exists.
* Small corpora saturate: with five demo documents, most configs hit
  1.00 and only the differences matter. Expect real spread as the corpus
  grows.

<div class="srag-checkpoint" markdown>
**Checkpoint: you can name what each layer is worth**

Point at one row of the ablation table and say what removing that layer cost
you on your corpus. If every row equals `full_deep`, the ablation is telling
you the corpus is too small or the ontology is not matching, and no weight you
change from here will be measurable.
</div>

## The judge, and why it is blind

Grading a generated answer happens in two independent passes:

**Pass 1, grounding (blind).** The judge sees the question, the answer,
and exactly the sources the assistant retrieved. It scores three
dimensions, 0 to 2 each: groundedness, meaning the sources support the
claims; citation accuracy, meaning the bracketed numbers point at sources
that really support the adjacent claim; and completeness, meaning the
answer used the relevant retrieved material. It never sees the reference
answer. A judge that does see it will happily reward an answer for
matching the reference even when the cited sources say no such thing.
That quietly converts your grounding metric into a paraphrase detector.

**Pass 2, correctness (reference-based).** A separate call compares the
answer against the expert reference, without the sources, and scores
factual agreement 0 to 2. The reference is a floor, not a ceiling: extra
correct detail is never penalized.

Both passes run at temperature 0, scores clamp to the rubric, and a
malformed judge response counts as a failure rather than getting silently
coerced. The judge prompts live in `domain/prompts/judge_grounding.md` and
`judge_correctness.md`. If you edit them, keep the blindness rules intact
and spot-check a handful of judged answers by hand afterward. The
rationale strings in `report.json` are kept for exactly that.

## Deciding whether to adopt snippet compression

Contextual snippet compression is an answer-generation condition, not a
retrieval ablation. Compare two real runs on the same corpus fingerprint,
question set, answer model, and independent judge model:

```bash
uv run sci-rag eval answers --snapshot uncompressed
uv run sci-rag eval answers --compressed --snapshot compressed
uv run sci-rag eval diff eval_results/<uncompressed>/report.json \
  eval_results/<compressed>/report.json
```

Each record contains measured prompt-token counts, compression fallbacks, and
dropped-source counts. The report gives median prompt tokens before and after;
the diff pairs judge dimensions and prompt-token deltas by question. Adopt the
domain default only when every judged dimension remains inside the comparison
confidence interval and median prompt tokens fall measurably. Otherwise leave
`compression.enabled: false` and record the rejection. A token reduction by
itself is not evidence that answer quality held.

The demo's own gate is worth reading in full, because it was run at three
settings and only one of them passed. Every run below used the v0.3 benchmark's
10 seed questions and one corpus snapshot, with real `gemini-2.5-flash` answers
and judging; all 10 graded with no evaluation failures.

| relevance_floor | groundedness | citation accuracy | completeness | correctness | median prompt tokens |
|---|---:|---:|---:|---:|---:|
| uncompressed | 2.00 | 2.00 | 2.00 | 1.60 | 1359 |
| **0.0** | **2.00** | **2.00** | 1.90 | 1.70 | **990** |
| 0.15 | 1.80 | 1.80 | 1.60 | 1.70 | 348 |
| 0.3 | 1.80 | 1.80 | 1.80 | 1.50 | 356 |

At 0.15 and above the gate fails, and it fails on two dimensions in particular:
groundedness and citation accuracy both leave their ceiling. That is the
signature of the relevance floor discarding sources, not of the summarizer
mangling them, and the counters confirm it: at 0.3, 61 sources were dropped
across the 10 questions with zero compression failures. Nothing failed to
summarize. The answer simply lost evidence it needed.

At 0.0, where every source is summarized and none dropped, the gate holds. Three
independent paired runs at that setting kept every judged dimension at or above
the uncompressed baseline while median prompt tokens fell 25% to 28%. So the
demo enables compression, at floor 0.0, and the model default floor matches it.

Two things generalize from this. First, summarizing a source and discarding one
are different trades, and the larger token saving is the unsafe one: dropping
bought 74% instead of 27%, and cost groundedness. Second, correctness moved
around a lot between identical baseline runs, from 1.30 to 1.80, so nothing here
rests on it. The three dimensions that sit at ceiling are what the gate turns on,
because a dimension pinned at 2.00 has nowhere to go but down if the change hurts.

[Benchmarks](benchmarks.md#contextual-compression-the-paired-gate) carries the
run's provenance, and these small-corpus results decide the demo default only,
not a general quality claim for other corpora.

## Calibrating the judge

The judged-answers table is only as citable as the judge behind it, so
the kit ships calibration as a workflow you re-run, not a one-off study:

1. Run an answers eval (`sci-rag eval answers`) and open its
   `report.json` in `eval_results/`.
2. Have a human read each generated answer (and its sources) **without**
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
("moderate", "substantial", and so on) is a standard reading aid, not a
target. A low kappa on a dimension is a real finding: the judge and a
human disagree there, and the agreement matrix shows how. Expect
unstable kappa below roughly 30 labeled answers; more labels, and labels
from a domain expert, make the number mean more.

The repo ships `domain/eval_calibration_labels.jsonl`: a seed label set
for the demo corpus, labeled by the kit's authors. It is marked
non-expert, and it earns that label: it demonstrates the workflow and pins
the format, nothing more. Domain-expert labels supersede it for any real
claim about judge reliability, and the BioCirV collaboration supplies
those for the flagship deployment.

## Sharing a run with someone who has no terminal

A domain expert asked to sanity-check ten judged answers should not have
to be talked through cloning anything. `sci-rag eval html` renders a run
as a single file you can attach to an email:

```bash
uv run sci-rag eval html eval_results/<run>
```

It writes `report.html` next to the report, or wherever `--output`
points. The page is self-contained: inline styles, no fonts, no scripts,
nothing fetched when it opens. That is deliberate. A page that fetches
anything renders differently for the recipient than for you, and
eventually renders as nothing behind a corporate firewall.

It leads with the provenance receipt, because a reader who cannot run the
command has no other way to find out which model produced what they are
reading. The small-sample and drafted-ground-truth warnings sit next to
the metrics, in the same place `report.md` puts them. `calibration.json`
is picked up automatically when it sits beside the report.

In an ablation table, a cell whose confidence interval overlaps the
baseline config is shaded, and one that clears it is bold. Overlapping
intervals are the most common way these tables get misread, and on a
single-digit corpus most cells will be shaded. That is the honest
reading, not a rendering failure.

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
broken chunker, layer, or seed file before it ships. It is also the
pattern to copy for your own corpus: freeze a small fixture corpus, pin
thresholds under your current numbers, and let regressions fail loudly.

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

When two people disagree about whether a change helped, the reports settle it.

<div class="srag-checkpoint" markdown>
**Checkpoint: the numbers are citable**

Your newest report names a corpus snapshot, a git commit, the answering and
grading models, and the enabled layers, and no question in it still carries the
`drafted` tag. A number missing any of those is a number you cannot put in a
methods section.
</div>

## Next steps

- Turn a measured improvement into a shipped default: [Methodology](methodology.md)
- See what the same harness produced on the demo corpus: [Benchmarks](benchmarks.md)
- Add a retrieval stage the ablation can measure: [Extend the kit](extend.md)
