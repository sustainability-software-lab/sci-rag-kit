---
title: Bring your own domain
description: Put your own documents into a knowledge base you can question, with your own concepts in the graph and your own questions scoring the result.
---

# Bring your own domain

By the end of this tutorial your own documents are in the database, your own
concepts are in the graph, and your own questions are scoring the result.
Nothing here requires editing Python. Your field lives in three places: a
folder of documents, one manifest file that describes them, and the
`domain/` folder that holds your concepts, prompts, and test questions.

<div class="srag-meta-strip">
  <div><strong>You'll build</strong>A knowledge base over your own documents</div>
  <div><strong>You'll need</strong>Documents on disk and a finished quickstart</div>
  <div><strong>Time</strong>An hour for a first pass, an afternoon for a careful one</div>
  <div><strong>Credentials</strong>Needed for the graph and cited answers; every other step has an offline route</div>
  <div><strong>Tested with</strong>v0.4</div>
</div>

Worked example throughout: you study membrane materials for water treatment,
and you have 60 PDFs of papers, theses, and technical reports.

The whole recipe fits on a card. Every step below explains one line of it:

```console title="Terminal"
$ uv run sci-rag draft manifest --folder data/raw      # 1. describe the documents
$ uv run sci-rag manifest lint data/corpus.jsonl        # 2. check the description
$ uv run sci-rag draft ontology --folder data/raw       # 3. name your concepts
$ uv run sci-rag build --manifest data/corpus.jsonl     # 4. ingest, then build the graph
$ uv run sci-rag draft questions --count 10             # 5. draft test questions
$ uv run sci-rag eval retrieval --ablation              # 6. measure
$ uv run sci-rag answer "a question in your field"      # 7. ask (needs a model credential)
```

Three of those commands draft a file for you to review. Each one also works
with no model credential at all: add `--print-prompt` to get the prompt,
answer it in any assistant you already use, and feed the reply back with
`--from-file reply.json`. [Drafting with a model](#drafting-with-a-model)
explains that pair once, because it is the same for all three.

## Before you start

| Requirement | Why | Check |
|---|---|---|
| A finished [quickstart](quickstart.md) | The database and its tables have to exist before anything here lands in them | `uv run sci-rag doctor` |
| Your documents on disk, under `data/raw/` | Every step below reads them | `ls data/raw \| wc -l` |
| A model credential, for two of the steps | The graph and the cited answer need one; ingestion, retrieval, and retrieval scoring do not | `grep SCI_RAG_GOOGLE .env` |
| A domain expert's attention, for one hour | Step 5 needs questions somebody can vouch for, and nothing substitutes | |

This tutorial has two end states, and you should know now which one is yours.

**With a model credential** you finish with your corpus ingested, a knowledge
graph over your own concepts, retrieval scored against your own questions,
judged answers, and a cited answer to a question in your field. That is the
full result, and the one to aim at.

**Without one** you finish with your corpus ingested, your concepts and
questions written and validated, and retrieval scored against those questions
on your own documents. Four commands stay out of reach: `graph extract`,
`graph communities`, `eval answers`, and `sci-rag answer`. The graph, the
judged answer metrics, and the cited answer are what a credential buys.
[Offline: what you can prove without a model](#offline-what-you-can-prove-without-a-model)
collects that route in one place.

## Step 0: run the setup wizard

If you got here from `sci-rag new`, setup already wrote the decisions you
made and the defaults behind them, and you can skip to step 1. Inside a
checkout you cloned or created from the GitHub template, run the same
wizard in place:

```bash
uv run sci-rag init --advanced
```

Advanced asks every applicable question. Run `uv run sci-rag init` to choose
between Quick and Advanced, or pass `--quick` to take the short path with
defaults for the rest. `--no-tty` gives plain numbered prompts, `--dry-run`
shows what setup would change without touching anything, and `--defaults`
answers every question with the shipped default.

Unlike `sci-rag new`, `sci-rag init` does not run the live credential check.
It still captures the key or project you enter and uses it directly if you
ask setup to draft the ontology. Run `uv run sci-rag doctor --probe`
afterward to confirm the provider accepts it.

Nothing setup writes is generated code, and nothing regenerates behind you.
You can re-run it later to change several answers at once, or edit the files
directly:

| Setup area | Where to review it |
|---|---|
| Project name, description | `domain/domain.yaml`, `pyproject.toml`, `README.md` |
| Credentials, models, embedding dimension | `.env`; a dimension change needs a migration and re-embedding |
| Ontology | `domain/domain.yaml`; step 3 below |
| Corpus source | `data/corpus.jsonl`, `data/dois.txt`, or a `make corpus` target; steps 1 and 2 below |
| PDF parser, reranker | `pyproject.toml` extras, `domain/domain.yaml` |
| Environment manager | `Makefile`, CI, `Dockerfile`, dev container, docs |
| Infrastructure, demo, license, Git | Ordinary project files |

## Step 1: collect your documents

Gather PDFs, HTML pages, Markdown, or plain-text files into `data/raw/`.
Three things make the rest of the tutorial go better:

* **Favor documents with answers in them.** Reviews, reports, and
  characterization papers beat commentary and slide decks.
* **Know your redistribution rights per document.** You are about to build a
  system that quotes these documents back to people. Public domain or CC BY
  is fine anywhere. A paywalled publisher PDF you legitimately hold is fine
  for your own instance, but it must be marked `restricted` so it can never
  surface on a service you share.
* **Start small.** The pipeline is happy from 5 documents to a few thousand.
  Begin with 20 to 50 good ones; a curated small corpus plus the evaluation
  step teaches you more than a dump.

In a hurry? `uv run sci-rag build data/raw` ingests a folder with no manifest
at all, marks every document `unknown` for rights, and builds the graph when a
credential is present. It is a fine first spike. It is not the route for a
corpus you will cite, because a re-ingest of the same file is skipped as a
duplicate, so rights and metadata you add later would never reach it. To
start over, delete the documents with `sci-rag corpus delete` and ingest
again from the manifest.

## Step 2: describe your documents

A manifest is one JSON line per document, and it is where citations and
rights come from. It lives at `data/corpus.jsonl`.

**Draft it, then review it.** The drafter reads each document's opening pages
through the same parsers ingestion uses and proposes title, authors, year,
DOI, journal, and a shared source bucket per document. Typing sixty of those
by hand is how a manifest ends up with three spellings of one journal.

```bash title="Terminal"
uv run sci-rag draft manifest --folder data/raw
```

Review `data/corpus.jsonl.proposed`, then move it into place, or re-run with
`--apply`.

**The rights column stays yours.** Every drafted row says `license_class:
unknown`, and the command tells you how many documents are waiting on a
decision. Retrieval treats `unknown` as unsafe: those documents stay
reachable from your own terminal, and drop out of any request that restricts
rights. A license sentence found verbatim in a document is quoted into
`license_source` as evidence for you to read.

Writing it by hand is a reasonable choice for a handful of documents. One JSON
object per line:

```jsonl title="data/corpus.jsonl"
{"path": "raw/lee-2021-fouling-review.pdf", "title": "Membrane Fouling Mechanisms: A Review", "authors": ["Lee, S.", "Park, J."], "year": 2021, "doi": "10.1000/example", "license_class": "open_commercial", "source": "journal_papers"}
{"path": "raw/epa-membrane-guidance.pdf", "title": "EPA Membrane Filtration Guidance Manual", "authors": ["US EPA"], "year": 2005, "license_class": "public", "source": "agency_reports"}
{"path": "raw/chen-thesis.pdf", "title": "Chen PhD Thesis", "year": 2023, "license_class": "restricted", "source": "theses"}
```

Field notes, which apply either way:

* `path` is relative to the manifest file. Only `path` is required.
* `license_class` is one of `public`, `open_commercial`,
  `open_noncommercial`, `restricted`, `unknown`. Aliases such as `CC-BY` and
  `cc0` are understood. When in doubt leave it out; `unknown` is the safe
  mistake.
* `source` is your own vocabulary for grouping, such as `journal_papers` or
  `agency_reports`. It becomes a retrieval filter, so choose 3 to 6
  meaningful buckets, not one per document.

Check it before you ingest it:

```bash
uv run sci-rag manifest lint data/corpus.jsonl
```

It reports every problem at once, with line numbers: files that are not
there, paths claimed twice, file types the parsers cannot read, entries with
no title, and misspelled keys the loader would ignore. It is strict about
`license_class` on purpose. A mistyped value such as `CC-BY-NC-ND-4.0` is
not rejected at ingestion; it is normalized to `unknown` and treated as
unsafe, which silently removes the document from results you expected it in.
The linter is the only place that difference is visible.

<div class="srag-checkpoint" markdown>
**Checkpoint: the manifest is clean and the rights are decided**

`manifest lint` reports no problems, and no row still says `license_class:
unknown` unless you meant it to. The count the linter prints is the number of
rights decisions you still owe.
</div>

## Step 3: name your concepts

`domain/domain.yaml` tells the graph builder which kinds of things matter in
your field (the entity types) and how they relate (the relation types).
Together those are called the ontology. The file ships configured for the
demo's agricultural types; replace them with yours.

**Draft it from your documents, then edit.** Once your documents are on disk
the field's vocabulary is already there, and the useful question stops being
what this field might contain and becomes what these documents talk about.

```bash title="Terminal"
uv run sci-rag draft ontology --folder data/raw
```

Review `domain/domain.yaml.proposed`, or re-run with `--apply`. After
ingestion you can drop `--folder` and the drafter samples the corpus in the
database instead. Already have an ontology you mostly like? `--refine` asks
only what the model would add and remove, with a reason for every removal.
`--cold` drafts from the description alone, without reading a document. Your
tuned `retrieval:` and `compression:` blocks carry over untouched either way.

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

Also update `query_classes` in the same file. List 3 to 5 kinds of question
your users ask, such as performance lookup, mechanism explanation, or
material comparison. Give each one a few trigger keywords and a one-line
instruction for how a document answering it would read. These steer the
retrieval layer that writes a hypothetical answer and searches for text that
resembles it.

## Step 4: build the knowledge base

One command ingests the manifest, then builds the graph:

```bash
uv run sci-rag build --manifest data/corpus.jsonl
```

Ingestion parses each document, splits it into chunks that keep their
section headings and tables intact, embeds the chunks, and stores everything
in Postgres. That part runs on any embedding setup, including the offline
one.

The graph is the part that needs a model. It reads every chunk and asks for
entities and relationships in your ontology, then clusters related entities
and writes a summary of each cluster. With no credential configured, `build`
says so and stops after ingestion; vector and keyword retrieval already work
at that point. The two graph steps are also available on their own, which is
how you add the graph later or re-run it after changing the ontology:

!!! note "Needs a model credential"

    ```bash
    uv run sci-rag graph extract
    uv run sci-rag graph communities
    ```

    Without a credential these exit 1 at the model boundary. Skip them, keep
    reading, and come back when you have one: nothing later in this tutorial
    depends on the graph except the graph's own checkpoint below.

Then look at what you have:

```bash
uv run sci-rag stats
uv run sci-rag retrieve "a question in your field" --profile interactive
```

<div class="srag-checkpoint" markdown>
**Checkpoint: the corpus and the graph both look like your field**

Three things to read, in this order.

`sci-rag stats` after ingest: the chunk count should look plausible, since a
dense 20-page PDF is usually 15 to 40 chunks, and the license classes should
be distributed the way you declared them.

`sci-rag retrieve "some question" --profile interactive`: the top chunks
should be recognizable, and the stage table tells you which layer found each
one.

`sci-rag stats` after the graph built, if it did: a 50-document corpus should
show entities in the low hundreds. Near zero means the ontology and the corpus
are talking past each other, usually because the types are too abstract or
the documents too thin. Thousands means the types are too loose. Either way,
go back to step 3, redraft with `--refine`, and re-run `graph extract`.

Offline, the first two readings are your checkpoint and there are no entities
to count. A corpus that ingests cleanly and retrieves recognizable chunks is
the whole of what this step can prove without a model, and it is worth
proving.
</div>

## Step 5: write seed questions, then measure

`domain/eval_seed_questions.jsonl` needs 10 to 20 questions a domain expert
can vouch for. This is the biggest manual step in the tutorial, and the one
where "vouch for" is doing the most work: these questions are what every
retrieval and answer metric is computed against.

**Draft the first ten, then sign off on each one.** Writing good seed
questions from a blank file is slow, and the drafter gives you something to
react to:

```bash title="Terminal"
uv run sci-rag draft questions --count 10
```

It samples real passages from your corpus, asks for questions grounded in
them, then verifies in Python that every quoted evidence phrase appears in a
passage belonging to a document the question names. Rows that fail are
dropped and reported.

Every drafted row carries a `drafted` tag, and the tag travels. While any
remain, `sci-rag eval retrieval` and `sci-rag eval answers` state in the
report that their ground truth is unreviewed and their numbers provisional.
Read each question, check it against the document it cites, then delete the
tag. That deletion is your sign-off, and nothing does it for you.

Already have questions people asked, especially ones the system fumbled?
`uv run sci-rag draft seed-from-answers questions.txt` takes one question per
line, answers each one, and proposes the reference answer and evidence phrases
from what that answer cited. It keeps a phrase only when it appears verbatim
in both the answer and the source, so the model's own prose never becomes
ground truth. Those rows arrive tagged `drafted` too.

Adding your own is the same file, one JSON object per line:

```jsonl title="domain/eval_seed_questions.jsonl"
{"id": "pfas-rejection", "question": "What PFAS rejection does a polyamide RO membrane achieve?", "reference_answer": "Above 99 percent for long-chain PFAS at typical seawater RO conditions, per Lee 2021.", "reference_titles": ["Membrane Fouling Mechanisms: A Review"], "evidence_phrases": ["99", "long-chain PFAS"], "tags": ["performance"]}
```

Three rules of thumb, either way. Pick evidence phrases distinctive enough
that finding them means finding the answer; numbers with units are perfect.
Include one or two questions whose answers span documents. And include one
question the corpus **cannot** answer, tagged `unanswerable`, so you can
check that the system admits a gap instead of filling it.

Then measure:

```bash
uv run sci-rag eval retrieval --ablation   # which layers contribute on your corpus
```

That one runs offline. It scores retrieval on your own corpus against your
own questions, and the table it prints scores each retrieval layer switched
off in turn, so you can see what each one contributes. Judging generated
answers is a second pass and needs a model:

!!! note "Needs a model credential"

    ```bash
    uv run sci-rag eval answers   # generated answers, graded for grounding and correctness
    ```

Read the table by comparing every row against `full_deep`, the row with every
layer on. If `no_graph` matches `full_deep`, your graph is not contributing
yet, usually an ontology problem, sometimes just a small corpus. Edit the
ontology or the corpus, re-run, compare: that loop is the honest path to a
good system, and the reports in `eval_results/` keep the receipts.
[Evaluate your pipeline](evaluation.md) explains every column.

## Step 6: adjust the prompts (optional)

Skim `domain/prompts/*.md`. They are deliberately short and readable, and for
most fields only two are worth touching:

* `entity_extraction.md`: keep the rules, adjust the example JSON names to
  your field so the model sees the register you expect.
* `answer.md`: add any domain-specific answer norms ("always report flux in
  LMH", "state the test conditions with every rejection value").

A model can reword them for your field while keeping the job identical:

```bash title="Terminal"
uv run sci-rag draft prompts entity_extraction
uv run sci-rag draft prompts answer
```

Every `$SLOT` has to survive, and the rewrite is rendered against dummy
values before it is written, because a template that lost a slot loads fine
and fails mid-run. Those two prompts are the only ones the command will
touch. The judge prompts, the compression prompt, and the drafting prompt are
refused by name, each with a reason: rewording a judge prompt would change
what every graded number means without breaking anything visibly.

Prompt wording moves every downstream number, so re-run
`sci-rag eval retrieval --ablation` after a rewrite and compare.

## Step 7: ask, then serve

With a credential, ask a question in your field:

!!! note "Needs a model credential"

    ```bash
    uv run sci-rag answer "a question in your field"
    ```

    Ask one the corpus cannot answer too. It should say so.

Then serve the same thing to people and agents:

```bash
uv run sci-rag serve
```

Before anyone else touches it, set API keys in `.env` (see `.env.example`)
and decide what an outside caller may see. A public or semi-public endpoint
should pin callers to `{"license_classes": ["public", "open_commercial"]}`
so your `restricted` and `unknown` documents stay internal.
[REST, MCP, and Python API](api.md) covers keys, scopes, and the agent
tools, and [Deploy on Google Cloud](deploy-gcp.md) covers putting it on
Cloud Run.

<div class="srag-checkpoint" markdown>
**Checkpoint: it is your knowledge base now**

Offline, ask a question in your own field through `POST /v1/query`. The
response should name documents you put there, with the license class you
declared and the retrieval layer that found each one. That is your end state,
and it is a real one: your corpus, your ontology, your questions, your
retrieval scores.

With a credential, the same question through `POST /v1/answer` or
`sci-rag answer` comes back with numbered citations pointing at those
documents.
</div>

## Drafting with a model

Three of the steps above draft a file: the manifest, the ontology, and the
seed questions. `sci-rag new` and `sci-rag init` can also draft the ontology
from a one-sentence description before any document exists, which is the
best guess available at that moment and nothing more.
Only `sci-rag new` checks the credential with a small live request first;
`sci-rag init` uses the key or project you enter without that check.

Every drafter offers the same three routes to the same validated file.

=== "Generate it"

    The configured model drafts it, and the reply is validated through the
    same model the loader uses, so a draft cannot be something the kit would
    later refuse to load.

    ```bash title="Terminal"
    uv run sci-rag draft questions --count 10
    ```

=== "Paste it into any assistant"

    No API key, no provider account. `--print-prompt` writes the fully
    rendered, corpus-grounded prompt to stdout. Paste it into whatever
    assistant you already use, save the reply, and feed it back.

    ```bash title="Terminal"
    uv run sci-rag draft questions --count 10 --print-prompt > prompt.txt
    # paste prompt.txt into an assistant, save the JSON reply as reply.json
    uv run sci-rag draft questions --count 10 --from-file reply.json
    ```

    Pass the same `--count` and `--folder` values to both commands: they
    decide which passages get sampled, and a reply is validated against
    the passages the assistant saw.

=== "Write it yourself"

    Nothing changes. Every file format is shown in full above, and a
    hand-written file is never touched by a drafter.

Four rules hold across all of them:

* **Nothing is overwritten.** A run writes `<file>.proposed` and prints a
  summary. Moving it into place is your step. `--apply` skips the proposal,
  and for seed questions it appends, never replaces. `--dry-run` writes
  nothing at all.
* **Rights are never guessed.** Every drafted manifest row says `unknown`.
* **Drafted questions stay labeled** until a person removes the `drafted`
  tag, and the evaluation reports repeat the label until then.
* **The judge's calibration labels are never drafted.**
  `domain/eval_calibration_labels.jsonl` exists to check the model judge
  against human judgment, and generating it with a model would destroy the
  only measurement it provides.

`sci-rag doctor` reports on all of this beside its usual checks: whether the
ontology is large enough to be worth extracting against, whether every
answerable seed question cites a document that exists, how many questions
still carry the `drafted` tag, and how many manifest rows nobody has
classified. Run it after changing anything in `domain/`.

## Offline: what you can prove without a model

The whole route, in order, with nothing that exits at a credential boundary.
Set `SCI_RAG_EMBEDDING_PROVIDER=local-hash` in `.env` first:

```bash
uv run sci-rag draft manifest --folder data/raw --print-prompt   # answer it yourself
uv run sci-rag draft manifest --folder data/raw --from-file reply.json --apply
uv run sci-rag manifest lint data/corpus.jsonl
uv run sci-rag draft ontology --folder data/raw --print-prompt
uv run sci-rag draft ontology --folder data/raw --from-file reply.json --apply
uv run sci-rag build --manifest data/corpus.jsonl
uv run sci-rag stats
uv run sci-rag retrieve "a question in your field" --profile interactive
uv run sci-rag draft questions --count 10 --print-prompt
uv run sci-rag draft questions --count 10 --from-file reply.json --apply
uv run sci-rag eval retrieval --ablation
uv run sci-rag serve
```

The offline embedder matches on words, not meaning, so treat its retrieval
scores as a floor on your own corpus and not as a comparison with a
credentialed run. What this route does not reach: the knowledge graph,
community summaries, judged answer metrics, and generated cited answers.

## The improvement loop

Corpus and ontology changes are cheap, and the evaluation reports are what
tell you a change helped. A rhythm that works: add or fix a handful of
documents, run `build` again (it only processes what is new), re-run the two
eval commands, read the diffs. When a real user asks a question the system
misses, add it as a seed question first, then go fix the miss.

## Next steps

- Read the evaluation table properly before you touch a retrieval weight: [Evaluate your pipeline](evaluation.md)
- Grow the corpus from a topic or a DOI list: [Run a corpus campaign](campaigns.md)
- Understand what a license class does to retrieval: [Evidence and rights](evidence-and-rights.md)
- Put the service somewhere your group can reach it: [Deploy on Google Cloud](deploy-gcp.md)
