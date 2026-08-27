# Bring your own domain

This tutorial covers specializing the kit to your own field. Budget an
afternoon for a first serious pass. Nothing here requires editing
Python; the domain is defined by the `domain/` folder, a corpus
manifest, and environment variables.

Worked example throughout: suppose you study membrane materials for
water treatment, and you have 60 PDFs of papers, theses, and technical
reports.

## Step 0: rebrand the template (optional but nice)

```bash
uv run python scripts/init_domain.py --name "Membrane Materials KB" \
    --description "Membrane chemistry, fouling, and performance for water treatment" --apply
```

That stamps your project name into the packaging metadata and the domain
profile, and resets the seed-question file to a guided blank. Without
`--apply` it just shows you what it would change.

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

## Step 2: write the corpus manifest

A manifest is one JSON line per document, and it is where licensing and
citations come from. Create `data/corpus.jsonl`:

```jsonl
{"path": "raw/lee-2021-fouling-review.pdf", "title": "Membrane Fouling Mechanisms: A Review", "authors": ["Lee, S.", "Park, J."], "year": 2021, "doi": "10.1000/example", "license_class": "open_commercial", "source": "journal_papers"}
{"path": "raw/epa-membrane-guidance.pdf", "title": "EPA Membrane Filtration Guidance Manual", "authors": ["US EPA"], "year": 2005, "license_class": "public", "source": "agency_reports"}
{"path": "raw/chen-thesis.pdf", "title": "Chen PhD Thesis", "year": 2023, "license_class": "restricted", "source": "theses"}
```

Field notes:

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

## Step 3: declare your ontology

Open `domain/domain.yaml`. This one file tells the graph extractor what
concepts matter in your field. Replace the demo's agricultural types
with yours:

```yaml
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

Also update `query_classes` in the same file: 3 to 5 kinds of questions
your users actually ask (performance lookup, mechanism explanation,
material comparison...), each with a few trigger keywords and a one-line
instruction for how a document answering it would read. These steer the
HyDE layer.

## Step 4: tune the prompts (lightly)

Skim `domain/prompts/*.md`. They are deliberately short and readable.
For most domains the only edits that matter are:

* `entity_extraction.md`: keep the rules, adjust the example JSON names
  to your field so the model sees the register you expect.
* `answer.md`: add any domain-specific answer norms ("always report flux
  in LMH", "state the test conditions with every rejection value").

Leave the judge prompts alone until you have read
[evaluation.md](evaluation.md); their blindness rules are load-bearing.

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

## Step 6: write seed questions, then measure

Replace `domain/eval_seed_questions.jsonl` with 10 to 20 questions a
domain expert can vouch for. Each line:

```jsonl
{"id": "pfas-rejection", "question": "What PFAS rejection does a polyamide RO membrane achieve?", "reference_answer": "Above 99 percent for long-chain PFAS at typical seawater RO conditions, per Lee 2021.", "reference_titles": ["Membrane Fouling Mechanisms: A Review"], "evidence_phrases": ["99", "long-chain PFAS"], "tags": ["performance"]}
```

Rules of thumb: pick evidence phrases distinctive enough that finding
them means finding the answer (numbers with units are perfect); include
one or two multi-hop questions whose answers span documents; include one
question the corpus canNOT answer, tagged `unanswerable`, as an honesty
probe.

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
`.env.example`), and decide your external license scope: a public or
semi-public endpoint should pin callers to
`{"license_classes": ["public", "open_commercial"]}` so your
`restricted` and `unknown` documents stay internal. The
[API reference](api.md) covers keys, scopes, and the MCP tools; the
[GCP guide](deploy-gcp.md) covers putting it on Cloud Run.

## The improvement loop

Corpus and ontology changes are cheap; the eval reports are the
evidence that a change helped. A workable rhythm: add or fix a handful
of documents, re-run ingest and graph, re-run the two eval commands,
read the diffs. When a real user asks a question the system misses,
add it as a seed question first, then fix the miss.
