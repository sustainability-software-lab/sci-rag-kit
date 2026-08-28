# Bring your own domain

This tutorial covers specializing the kit to your own field. Budget an
afternoon for a first serious pass. Nothing here requires editing
Python; the domain is defined by the `domain/` folder, a corpus
manifest, and environment variables.

Worked example throughout: suppose you study membrane materials for
water treatment, and you have 60 PDFs of papers, theses, and technical
reports.

If you got here from `sci-rag-new`, the wizard already asked you most of
this. Every answer landed in a file you can keep editing. Nothing here is
generated code, and nothing regenerates behind you:

| What it asked | Where the answer went | How to change it |
|---|---|---|
| project name, description | `domain/domain.yaml`, `pyproject.toml`, `README.md` | edit the files, or re-run the wizard |
| credentials, models, embedding dimension | `.env` | edit `.env`; changing the dimension needs a migration and re-embedding |
| ontology | `domain/domain.yaml` | step 3 below |
| corpus source | `data/corpus.jsonl`, `data/dois.txt`, or a `make corpus` target | steps 1 and 2 below |
| PDF parser, reranker | `pyproject.toml` extras, `domain/domain.yaml` | step 5 below, and [Configuration](configuration.md) |
| environment manager | `Makefile`, CI, `Dockerfile`, dev container, docs | re-run the wizard; it renders all five together |
| license, git | `LICENSE`, the initial commit | ordinary files |

The rest of this tutorial is the same work done by hand. Read it either
way: the wizard picks defaults, and knowing which ones is how you decide
whether to keep them.

## Step 0: run the setup wizard

```bash
uv run sci-rag init
```

Same questions as `sci-rag-new`, run against the checkout you are already
standing in. Every question has a default, so pressing Enter through the
session leaves you with something that runs offline. `--dry-run` shows
what it would change without touching anything; `--defaults` skips the
asking entirely.

You can re-run it later. That is how you change several answers at once.

Want only the name and description stamped in, with the demo ontology's
guided comments left intact? The narrow path still works:

```bash
uv run python scripts/init_domain.py --name "Membrane Materials KB" \
    --description "Membrane chemistry, fouling, and performance for water treatment" --apply
```

Without `--apply` it just shows you what it would change.

## Step 1: collect your documents

Gather PDFs, Markdown, or plain-text files into `data/raw/`. Advice
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

## Step 2: the corpus manifest

A manifest is one JSON line per document, and it is where licensing and
citations come from. It lives at `data/corpus.jsonl`.

=== "Generate it"

    Reads each document's opening pages through the same parsers ingestion
    uses, and proposes a manifest with title, authors, year, DOI, journal, and
    a shared source bucket per document.

    ```bash title="Terminal"
    uv run sci-rag draft manifest --folder data/raw
    ```

    Review `data/corpus.jsonl.proposed`, then move it into place, or re-run
    with `--apply`. No API key? Add `--print-prompt`, paste the result into any
    assistant, and feed the reply back with `--from-file`. See
    [LLM-assisted setup](llm-assisted-setup.md).

    **The rights column is yours.** Every drafted row says `license_class:
    unknown`, which is the fail-closed default, and the command tells you how
    many documents need a decision. A license sentence found verbatim in a
    document is quoted into `license_source` as evidence for you to read. The
    field reference below is what you are editing.

=== "Write it yourself"

    Create `data/corpus.jsonl`:

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

## Step 3: declare your ontology

`domain/domain.yaml` tells the graph extractor what concepts matter in your
field. It ships configured for the demo's agricultural types; replace them with
yours.

=== "Generate it"

    Once documents are on disk, the field's own vocabulary is right there, so
    the useful question is not what this field might contain but what these
    documents actually talk about.

    ```bash title="Terminal"
    uv run sci-rag draft ontology --from-corpus
    ```

    Review `domain/domain.yaml.proposed`, or re-run with `--apply`. Already
    have an ontology you mostly like? `--refine` asks only what the model would
    add and remove, with a reason for every removal. Your tuned `retrieval:`
    and `compression:` blocks are carried over untouched either way.

    This is also the fix for the symptom in step 5 below: near zero entities
    after `graph extract` means the ontology and the corpus are talking past
    each other.

=== "Write it yourself"

    Open `domain/domain.yaml` and replace the demo's types:

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

How to choose well, either way:

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

=== "Generate it"

    ```bash title="Terminal"
    uv run sci-rag draft prompts entity_extraction
    uv run sci-rag draft prompts answer
    ```

    Rewords the template in your field's terms while keeping the job identical:
    every `$SLOT` must survive, the output contract must not move, and the
    rewrite is re-rendered against dummy values before it is written, because a
    template that lost a slot loads fine and fails mid-run.

    Only those two commands exist. The judge prompts and the compression prompt
    are refused by name, with a reason.

=== "Write it yourself"

    * `entity_extraction.md`: keep the rules, adjust the example JSON names
      to your field so the model sees the register you expect.
    * `answer.md`: add any domain-specific answer norms ("always report flux
      in LMH", "state the test conditions with every rejection value").

Leave the judge prompts alone until you have read
[evaluation.md](evaluation.md); their blindness rules are load-bearing. Prompt
wording moves every downstream number, so re-run
`sci-rag eval retrieval --ablation` after a rewrite and compare.

## Step 5: ingest and build

```bash
uv run sci-rag ingest --manifest data/corpus.jsonl
uv run sci-rag graph extract
uv run sci-rag graph communities
uv run sci-rag stats
```

Sanity checks along the way:

* `sci-rag stats` after ingest: does the chunk count look right (a dense
  20-page PDF is typically 15 to 40 chunks)? Are your license classes
  distributed the way you declared?
* `sci-rag retrieve "some question" --profile interactive`: do the top
  chunks look sane? The stage table shows you which layer found what.
* After `graph extract`: `stats` should show entities in the low
  hundreds for a 50-document corpus. Near zero means the ontology and
  the corpus are talking past each other (types too abstract, or
  documents too thin); thousands means the types are too loose.

## Step 6: seed questions, then measure

`domain/eval_seed_questions.jsonl` needs 10 to 20 questions a domain expert can
vouch for. This is the biggest manual step in the tutorial, and the one where
"vouch for" is doing the most work: these questions are what every retrieval
and answer metric is computed against.

=== "Generate it"

    ```bash title="Terminal"
    uv run sci-rag draft questions --count 10
    ```

    Samples real passages from your corpus, asks for questions grounded in
    them, and then verifies in Python that every quoted evidence phrase
    actually appears in a passage belonging to a document the question names.
    Rows that fail are dropped and reported.

    Every drafted row carries a `drafted` tag, and it travels: while any
    remains, `sci-rag eval retrieval` and `sci-rag eval answers` say in the
    report that their ground truth is unreviewed and their numbers provisional.
    Read each question, check it against the document it cites, then delete the
    tag. That deletion is your sign-off, and nothing does it for you.

=== "Write it yourself"

    Replace the file with your own lines:

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
uv run sci-rag eval answers                # generated answers, graded by the blind judge
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
[API reference](api.md) covers keys, scopes, and the MCP tools; the
[GCP guide](deploy-gcp.md) covers putting it on Cloud Run.

## The improvement loop

Corpus and ontology changes are cheap; the eval reports are the
evidence that a change helped. A workable rhythm: add or fix a handful
of documents, re-run ingest and graph, re-run the two eval commands,
read the diffs. When a real user asks a question the system misses,
add it as a seed question first, then fix the miss.
