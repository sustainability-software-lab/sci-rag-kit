---
title: Bring your own domain
description: Replace the demo ontology, prompts, corpus manifest, and seed questions with your own field, and prove the pipeline still works.
---

# Bring your own domain

By the end of this tutorial your own literature is in the database, your
own concepts are in the graph, and your own questions are scoring the
result. None of it requires editing Python. The domain is a folder, a
corpus manifest, and a few environment variables.

<div class="srag-meta-strip">
  <div><strong>You'll build</strong>A knowledge base over your own corpus</div>
  <div><strong>You'll need</strong>Documents on disk and a working quickstart</div>
  <div><strong>Time</strong>An afternoon for a first serious pass</div>
  <div><strong>Credentials</strong>Needed for the graph and cited answers; steps 1 to 6 have an offline route</div>
  <div><strong>Tested with</strong>v0.4</div>
</div>

Worked example throughout: you study membrane materials for water
treatment, and you have 60 PDFs of papers, theses, and technical reports.

## Before you start

| Requirement | Why | Check |
|---|---|---|
| A finished [quickstart](quickstart.md) | The database and schema have to exist before anything here lands in them | `uv run sci-rag doctor` |
| Your documents on disk, usually under `data/raw/` | Every step below reads them | `ls data/raw \| wc -l` |
| A model credential | Four steps need one; the rest of the tutorial does not. See the two routes below | `grep SCI_RAG_GOOGLE .env` |
| A domain expert's attention, for one hour | Step 6 needs questions somebody can vouch for, and nothing substitutes | |

This tutorial has two end states, and you should know now which one is yours.

**With a model credential** you finish with your corpus ingested, a knowledge
graph over your own ontology, community summaries, retrieval scored against
your own questions, judged answers, and a cited answer to a question in your
field. That is the full result, and it is the one to aim at.

**Without one** you finish with your corpus ingested, your ontology and seed
questions written and validated, and retrieval scored against those questions
on your own documents. Four commands are unavailable: `graph extract`,
`graph communities`, `eval answers`, and `sci-rag answer`. The graph, the
judged answer metrics, and the cited answer are what a credential buys. The
drafters stay available either way through `--print-prompt` and `--from-file`,
which render the corpus-grounded prompt for you to answer yourself and read
the reply back through the same validation.

Every step below marks the parts that need a credential, and
[Offline: what you can prove without a model](#offline-what-you-can-prove-without-a-model)
collects the offline route in one place.

If you got here from `sci-rag new`, setup already wrote the decisions you
made and the defaults behind them. Quick asks for six setup decisions, plus
the credential value required by the selected mode. It defaults the repository
name, author, Python version, models, embedding dimension, ontology behavior,
source details, parser, reranker, infrastructure, demo content, license, and
Git initialization. Advanced asks every applicable question instead. Offline
setup keeps the worked example ontology. A credentialed Quick setup drafts one
from the description after the credential check succeeds; continuing after a
failed check keeps the example.

Nothing here is generated code, and nothing regenerates behind you:

| Setup area | Where to review it |
|---|---|
| Project name, description | `domain/domain.yaml`, `pyproject.toml`, `README.md` |
| Credentials, models, embedding dimension | `.env`; a dimension change needs a migration and re-embedding |
| Ontology | `domain/domain.yaml`; step 3 below |
| Corpus source | `data/corpus.jsonl`, `data/dois.txt`, or a `make corpus` target; steps 1 and 2 below |
| PDF parser, reranker | `pyproject.toml` extras, `domain/domain.yaml`; step 5 below |
| Environment manager | `Makefile`, CI, `Dockerfile`, dev container, docs |
| Infrastructure, demo, license, Git | Ordinary project files |

The rest of this tutorial does the domain work deliberately. Read it either
way: knowing what setup chose is how you decide whether to keep it.

## Step 0: run the setup wizard

```bash
uv run sci-rag init --advanced
```

This tutorial uses Advanced because it exposes every applicable project choice.
Run `uv run sci-rag init` to choose Quick or Advanced interactively, or pass
`--quick` to select the short path directly. Pass `--no-tty` when you want plain
numbered prompts instead of the terminal menu. `--dry-run` shows what setup
would change without touching anything; `--defaults` skips the questions and
uses the shipped defaults.

Unlike `sci-rag new`, `sci-rag init` does not run the live credential check.
It still captures the selected key or project and uses it directly if you ask
setup to draft the ontology. Run `uv run sci-rag doctor --probe` afterward when
you need to verify that the provider accepts it.

You can re-run it later. That is how you change several answers at once.

Want only the name and description stamped in, with the demo ontology's
guided comments left intact? The narrow path still works:

```bash
uv run python scripts/init_domain.py --name "Membrane Materials KB" \
    --description "Membrane chemistry, fouling, and performance for water treatment" --apply
```

Without `--apply` it just shows you what it would change.

## Step 1: collect your documents

Gather PDFs, HTML pages, Markdown, or plain-text files into `data/raw/`. Advice
learned the hard way:

* **Favor documents with answers in them.** Reviews, reports, and
  characterization papers beat commentary and slide decks.
* **Know your redistribution rights per document.** You are about to
  build a system that quotes these documents back to people. Public
  domain or CC-BY? Fine anywhere. A paywalled publisher PDF you
  legitimately hold? Fine for your internal instance, but it must be
  marked `restricted` so it can never surface on an open endpoint.
* **Volume guidance.** The pipeline is happy from 5 documents to a few
  thousand. Start with 20 to 50 good ones; you will learn more from a
  curated small corpus plus the evaluation harness than from a dump.

## Step 2: write the corpus manifest

A manifest is one JSON line per document, and it is where licensing and
citations come from. It lives at `data/corpus.jsonl`.

**Draft it, then review it.** The drafter reads each document's opening pages
through the same parsers ingestion uses, and proposes title, authors, year,
DOI, journal, and a shared source bucket per document. Typing sixty of those
by hand is how a manifest ends up with three spellings of one journal.

```bash title="Terminal"
uv run sci-rag draft manifest --folder data/raw
```

Review `data/corpus.jsonl.proposed`, then move it into place, or re-run with
`--apply`. No API key is fine: `--print-prompt` gives you the prompt to paste
into any assistant, and `--from-file` reads the reply back through identical
validation. [LLM-assisted setup](llm-assisted-setup.md) has that workflow in
full.

**The rights column stays yours.** Every drafted row says `license_class:
unknown`, the fail-closed default, and the command tells you how many
documents are waiting on a decision. A license sentence found verbatim in a
document is quoted into `license_source` as evidence for you to read.

Writing it by hand is a reasonable choice for a handful of documents. One JSON
object per line, in `data/corpus.jsonl`:

```jsonl title="data/corpus.jsonl"
{"path": "raw/lee-2021-fouling-review.pdf", "title": "Membrane Fouling Mechanisms: A Review", "authors": ["Lee, S.", "Park, J."], "year": 2021, "doi": "10.1000/example", "license_class": "open_commercial", "source": "journal_papers"}
{"path": "raw/epa-membrane-guidance.pdf", "title": "EPA Membrane Filtration Guidance Manual", "authors": ["US EPA"], "year": 2005, "license_class": "public", "source": "agency_reports"}
{"path": "raw/chen-thesis.pdf", "title": "Chen PhD Thesis", "year": 2023, "license_class": "restricted", "source": "theses"}
```

Field notes, which apply either way:

* `path` is relative to the manifest file. Only `path` is required.
* `license_class` is one of `public`, `open_commercial`,
  `open_noncommercial`, `restricted`, `unknown` (aliases like `CC-BY`
  and `cc0` are understood). When in doubt, leave it out; the default
  `unknown` is treated as unsafe, which is the safe mistake.
* `source` is your own vocabulary for grouping ("journal_papers",
  "agency_reports"). It becomes a retrieval filter, so choose 3 to 6
  meaningful buckets rather than one per document.

You can also skip the manifest and run `sci-rag ingest data/raw`, which
auto-builds entries with everything defaulted; fine for a first spike,
not for a corpus you will cite.

Check it before you ingest it:

```bash
uv run sci-rag manifest lint data/corpus.jsonl
```

It reports every problem at once, with line numbers, rather than one per
failed document partway through an ingest run: files that are not there,
paths claimed twice, file types the parsers cannot read, entries with no
title, and misspelled keys the loader would ignore. It is strict about
`license_class` on purpose. An unrecognized value is not rejected at
ingestion, it is normalized to `unknown` and scoped as unsafe, so a
mistyped `CC-BY-NC-ND-4.0` silently removes a document from results you
expected it in. The linter is the only place that difference is visible.

<div class="srag-checkpoint" markdown>
**Checkpoint: the manifest is clean and the rights are decided**

`manifest lint` reports no problems, and no row still says `license_class:
unknown` unless you meant it to. Every `unknown` is a document retrieval will
treat as unsafe, so the count the linter prints is the number of decisions you
still owe.
</div>

## Step 3: declare your ontology

`domain/domain.yaml` tells the graph extractor what concepts matter in your
field. It ships configured for the demo's agricultural types; replace them with
yours.

**Draft it from the corpus, then edit.** Once your documents are on disk the
field's vocabulary is already there, and the useful question stops being what
this field might contain and becomes what these documents talk about.

```bash title="Terminal"
uv run sci-rag draft ontology --from-corpus
```

Review `domain/domain.yaml.proposed`, or re-run with `--apply`. Already have an
ontology you mostly like? `--refine` asks only what the model would add and
remove, with a reason for every removal. Your tuned `retrieval:` and
`compression:` blocks carry over untouched either way.

This is also the fix for the symptom in step 5 below. Near zero entities after
`graph extract` means the ontology and the corpus are talking past each other.

Whichever way you get there, you end up editing this file by hand, so here is
what it looks like filled in:

```yaml title="domain/domain.yaml"
name: "Membrane Materials KB"
description: >
  Membrane chemistry, fouling behavior, and separation performance for
  water treatment applications.

entity_types:
  - name: Membrane
    description: "A membrane type or product (thin-film composite, ceramic UF)"
  - name: Material
    description: "A polymer, ceramic, or coating material (polyamide, PVDF, graphene oxide)"
  - name: Contaminant
    description: "A species being removed (NaCl, boron, PFAS, natural organic matter)"
  - name: FoulingMechanism
    description: "A fouling mode (scaling, biofouling, organic adsorption)"
  - name: Process
    description: "A treatment process or operation (reverse osmosis, backwashing)"
  - name: PerformanceMetric
    description: "A measured performance quantity (flux, rejection, permeability)"
  - name: Treatment
    description: "A cleaning or surface modification (chlorination, zwitterionic coating)"

relation_types:
  - name: MADE_OF
    description: "Membrane is made of material"
  - name: REMOVES
    description: "Membrane or process removes contaminant"
  - name: SUFFERS_FROM
    description: "Membrane or material suffers from fouling mechanism"
  - name: MITIGATED_BY
    description: "Fouling mechanism is mitigated by treatment"
  - name: MEASURED_AT
    description: "Metric measured at a condition or value"
  - name: IMPROVES
    description: "Treatment or material improves a performance metric"
```

How to choose well:

* **6 to 15 entity types.** Fewer and the graph is mush; more and the
  extractor dithers. Ask: what column headings would an expert use to
  organize a spreadsheet of this field's facts?
* **Descriptions are prompts.** The extraction model sees them verbatim.
  Concrete examples in parentheses do more work than abstract phrasing.
* **Relations read as sentences.** "source RELATION target" should be
  sayable out loud: "polyamide SUFFERS_FROM chlorine degradation".

Also update `query_classes` in the same file. List 3 to 5 kinds of
question your users actually ask, such as performance lookup, mechanism
explanation, or material comparison. Give each one a few trigger keywords
and a one-line instruction for how a document answering it would read.
These steer the HyDE layer.

## Step 4: tune the prompts (lightly)

Skim `domain/prompts/*.md`. They are deliberately short and readable, and for
most domains only two of them are worth touching.

**Let the drafter reword them, then read the diff.** It keeps the job
identical while moving the register into your field:

```bash title="Terminal"
uv run sci-rag draft prompts entity_extraction
uv run sci-rag draft prompts answer
```

Every `$SLOT` has to survive, the output contract cannot move, and the rewrite
is re-rendered against dummy values before it is written, because a template
that lost a slot loads fine and fails mid-run. Only those two commands exist.
The judge prompts and the compression prompt are refused by name, with a
reason.

Editing them yourself is a small job, and there are only two things worth
doing:

* `entity_extraction.md`: keep the rules, adjust the example JSON names to
  your field so the model sees the register you expect.
* `answer.md`: add any domain-specific answer norms ("always report flux in
  LMH", "state the test conditions with every rejection value").

Leave the judge prompts alone until you have read
[Evaluate your pipeline](evaluation.md); their blindness rules are load-bearing. Prompt
wording moves every downstream number, so re-run
`sci-rag eval retrieval --ablation` after a rewrite and compare.

## Step 5: ingest and build

Ingestion and retrieval run on any embedding provider, including the offline
one:

```bash
uv run sci-rag ingest --manifest data/corpus.jsonl
uv run sci-rag stats
uv run sci-rag retrieve "a question in your field" --profile interactive
```

The graph is the part that needs a model. It reads every chunk and asks for
entities and relationships in your ontology, so there is no offline lane for
it:

!!! note "Needs a model credential"

    ```bash
    uv run sci-rag graph extract
    uv run sci-rag graph communities
    uv run sci-rag stats
    ```

    Without a credential these exit 1 at the model boundary. Skip them, keep
    reading, and come back when you have one: nothing later in this tutorial
    depends on the graph except the graph's own checkpoint below.

<div class="srag-checkpoint" markdown>
**Checkpoint: the corpus and the graph both look like your field**

Three things to read, in this order.

`sci-rag stats` after ingest: the chunk count should look plausible, since a
dense 20-page PDF is usually 15 to 40 chunks, and the license classes should be
distributed the way you declared them.

`sci-rag retrieve "some question" --profile interactive`: the top chunks should
be recognizable, and the stage table tells you which layer found each one.

`sci-rag stats` after `graph extract`, if you ran it: a 50-document corpus
should show entities in the low hundreds. Near zero means the ontology and the
corpus are talking past each other, usually because the types are too abstract
or the documents too thin. Thousands means the types are too loose. Either way,
go back to step 3 and redraft with `--refine`.

Offline, the first two readings are your checkpoint and there are no entities
to count. A corpus that ingests cleanly and retrieves recognizable chunks is
the whole of what this step can prove without a model, and it is worth
proving.
</div>

## Step 6: write seed questions, then measure

`domain/eval_seed_questions.jsonl` needs 10 to 20 questions a domain expert can
vouch for. This is the biggest manual step in the tutorial, and the one where
"vouch for" is doing the most work: these questions are what every retrieval
and answer metric is computed against.

**Draft the first ten, then sign off on each one.** Writing good seed questions
from a blank file is slow, and the drafter gives you something to react to:

```bash title="Terminal"
uv run sci-rag draft questions --count 10
```

It samples real passages from your corpus, asks for questions grounded in them,
then verifies in Python that every quoted evidence phrase actually appears in a
passage belonging to a document the question names. Rows that fail are dropped
and reported.

Every drafted row carries a `drafted` tag, and the tag travels. While any
remain, `sci-rag eval retrieval` and `sci-rag eval answers` state in the report
that their ground truth is unreviewed and their numbers provisional. Read each
question, check it against the document it cites, then delete the tag. That
deletion is your sign-off, and nothing does it for you.

Adding your own is the same file, one JSON object per line:

```jsonl title="domain/eval_seed_questions.jsonl"
{"id": "pfas-rejection", "question": "What PFAS rejection does a polyamide RO membrane achieve?", "reference_answer": "Above 99 percent for long-chain PFAS at typical seawater RO conditions, per Lee 2021.", "reference_titles": ["Membrane Fouling Mechanisms: A Review"], "evidence_phrases": ["99", "long-chain PFAS"], "tags": ["performance"]}
```

Three rules of thumb, either way. Pick evidence phrases distinctive enough that
finding them means finding the answer, where numbers with units are
perfect. Include one or two multi-hop questions whose answers span
documents. And include one question the corpus **cannot** answer, tagged
`unanswerable`, as an honesty probe.

Then:

```bash
uv run sci-rag eval retrieval --ablation   # which layers contribute on your corpus
```

That one runs offline. It scores retrieval on your own corpus against your own
questions, and the ablation table is where the improvement loop below starts.
Judging generated answers is a second pass and it needs a model:

!!! note "Needs a model credential"

    ```bash
    uv run sci-rag eval answers   # generated answers, graded by the blind judge
    ```

Read the ablation table by comparing every row against `full_deep`. If
`no_graph` matches `full_deep`, your graph is not contributing yet
(usually an ontology problem, sometimes just a small corpus). This
feedback loop, edit ontology or corpus, re-run, compare, is the honest
path to a good system, and the reports in `eval_results/` keep the
receipts.

## Step 7: serve and share

```bash
uv run sci-rag serve
```

Before anyone else touches it, set API keys in `.env` (see
`.env.example`) and decide your external license scope. A public or
semi-public endpoint should pin callers to
`{"license_classes": ["public", "open_commercial"]}`, so your `restricted`
and `unknown` documents stay internal. The
[REST, MCP, and Python API](api.md) covers keys, scopes, and the MCP tools, and
[Deploy on Google Cloud](deploy-gcp.md) covers putting it on Cloud Run.

<div class="srag-checkpoint" markdown>
**Checkpoint: it is your knowledge base now**

Offline, ask a question in your own field through `POST /v1/query`. The
response should name documents you put there, with the license class you
declared and the retrieval layer that found each one. That is your end state,
and it is a real one: your corpus, your ontology, your questions, your
retrieval scores.

With a credential, the same question through `POST /v1/answer` or
`sci-rag answer` comes back with numbered citations pointing at those
documents. Ask one the corpus cannot answer, and it should say so.
</div>

!!! note "Needs a model credential"

    ```bash
    uv run sci-rag answer "a question in your field"
    ```

## Offline: what you can prove without a model

The whole route, in order, with nothing that exits at a credential boundary:

```bash
uv run sci-rag draft manifest --folder data/raw --print-prompt   # answer it yourself
uv run sci-rag draft manifest --folder data/raw --from-file reply.json --apply
uv run sci-rag manifest lint data/corpus.jsonl
uv run sci-rag draft ontology --from-corpus --print-prompt
uv run sci-rag draft ontology --from-corpus --from-file reply.json --apply
uv run sci-rag ingest --manifest data/corpus.jsonl
uv run sci-rag stats
uv run sci-rag retrieve "a question in your field" --profile interactive
uv run sci-rag draft questions --count 10 --print-prompt
uv run sci-rag draft questions --count 10 --from-file reply.json --apply
uv run sci-rag eval retrieval --ablation
uv run sci-rag serve
```

Set `SCI_RAG_EMBEDDING_PROVIDER=local-hash` first. Its similarity is lexical
rather than semantic, so treat the retrieval scores as a floor on your own
corpus and not as a comparison with a credentialed run.

What this route does not reach: the knowledge graph, community summaries,
judged answer metrics, and generated cited answers. Those are the four
commands gated above, and they are what a credential buys.

## The improvement loop

Corpus and ontology changes are cheap, and the eval reports are what tell
you a change helped. A rhythm that works: add or fix a handful of
documents, re-run ingest and graph, re-run the two eval commands, read the
diffs. When a real user asks a question the system misses, add it as a seed
question first, then go fix the miss.

## Next steps

- Get more out of the drafters, including the no-credentials workflow: [LLM-assisted setup](llm-assisted-setup.md)
- Read the ablation table properly before you touch a retrieval weight: [Evaluate your pipeline](evaluation.md)
- Grow the corpus from a topic or a DOI list: [Run a corpus campaign](campaigns.md)
- Put the service somewhere your group can reach it: [Deploy on Google Cloud](deploy-gcp.md)
