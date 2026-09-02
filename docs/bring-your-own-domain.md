---
title: Bring your own domain
description: Put your own documents into a knowledge base you can question, with your concepts in the graph and your questions scoring the result.
---

# Bring your own domain

At the end of this tutorial your documents are in the database, your concepts are in the graph, and your questions are scoring the result. None of it requires editing Python. Your field lives in a folder of documents, one manifest file that describes them, and the `domain/` folder.

<div class="srag-meta-strip">
  <div><strong>You'll build</strong>A knowledge base over your own documents</div>
  <div><strong>You'll need</strong>Documents on disk and a finished quickstart</div>
  <div><strong>Time</strong>An hour for a first pass; an afternoon for a careful one</div>
  <div><strong>Credentials</strong>Needed for the graph and cited answers; every other step has an offline route</div>
  <div><strong>Tested with</strong>v0.4</div>
</div>

The worked example: you study membrane materials for water treatment and have 60 PDFs of papers, theses, and technical reports.

The whole recipe is seven commands. Each step below explains one line.

```console title="Terminal"
$ uv run sci-rag draft manifest --folder data/raw      # 1. describe the documents
$ uv run sci-rag manifest lint data/corpus.jsonl        # 2. check the description
$ uv run sci-rag draft ontology --folder data/raw       # 3. name your concepts
$ uv run sci-rag build --manifest data/corpus.jsonl     # 4. ingest, then build the graph
$ uv run sci-rag draft questions --count 10             # 5. draft test questions
$ uv run sci-rag eval retrieval --ablation              # 6. measure
$ uv run sci-rag answer "a question in your field"      # 7. ask (needs a model credential)
```

Three of these commands draft a file for you to review. Each one also works without a model credential: add `--print-prompt` to get the prompt, answer it in any assistant you already use, and feed the reply back with `--from-file reply.json`. [Drafting with a model](#drafting-with-a-model) explains that pair once.

## Before you start

| Requirement | Why | Check |
|---|---|---|
| A finished [quickstart](quickstart.md) | The database and its tables must exist first | `uv run sci-rag doctor` |
| Your documents under `data/raw/` | Every step reads them | `ls data/raw \| wc -l` |
| A model credential, for two steps | The graph and the cited answer need one; ingestion, retrieval, and retrieval scoring do not | `grep SCI_RAG_GOOGLE .env` |
| A domain expert, for one hour | Step 5 needs questions somebody can vouch for | |

There are two end states.

**With a model credential** you finish with your corpus ingested, a knowledge graph over your own concepts, retrieval scored against your own questions, judged answers, and a cited answer to a question in your field.

**Without one** you finish with your corpus ingested, your concepts and questions written and validated, and retrieval scored against those questions. Four commands need a credential: `graph extract`, `graph communities`, `eval answers`, and `sci-rag answer`. [Offline: what you can prove without a model](#offline-what-you-can-prove-without-a-model) lists the route in one place.

## Step 0: run the setup wizard

If you came from `sci-rag new`, setup already wrote your decisions and the defaults behind them. Skip to step 1.

In a checkout you cloned or created from the GitHub template, run the same wizard in place:

```bash
uv run sci-rag init --advanced
```

Advanced asks every applicable question. `uv run sci-rag init` lets you choose between Quick and Advanced, and `--quick` takes the short path with defaults for the rest. `--no-tty` gives plain numbered prompts. `--dry-run` shows what setup would change without writing. `--defaults` answers every question with the shipped default.

Unlike `sci-rag new`, `sci-rag init` does not run the live credential check. It uses the key or project you enter as given. Run `uv run sci-rag doctor --probe` afterward to confirm the provider accepts it.

Setup writes ordinary files, and nothing regenerates behind you. Re-run it to change several answers at once, or edit the files directly:

| Setup area | Where to review it |
|---|---|
| Project name, description | `domain/domain.yaml`, `pyproject.toml`, `README.md` |
| Credentials, models, embedding dimension | `.env`; a dimension change needs a migration and re-embedding |
| Ontology | `domain/domain.yaml`; step 3 |
| Corpus source | `data/corpus.jsonl`, `data/dois.txt`, or a `make corpus` target; steps 1 and 2 |
| PDF parser, reranker | `pyproject.toml` extras, `domain/domain.yaml` |
| Environment manager | `Makefile`, CI, `Dockerfile`, dev container, docs |
| Infrastructure, demo, license, Git | Ordinary project files |

## Step 1: collect your documents

Put PDFs, HTML pages, Markdown, or plain-text files in `data/raw/`.

- Choose documents that contain answers. Reviews, reports, and characterization papers hold more retrievable facts than commentary and slide decks.
- Know each document's redistribution rights. The system quotes these documents back to people. A public-domain or CC BY document is fine anywhere. A paywalled PDF you legitimately hold is fine for your own instance, but mark it `restricted` so it never appears on a service you share.
- Start with 20 to 50 good documents. The pipeline handles 5 to a few thousand, and a small curated set plus the evaluation step teaches you more than a dump.

For a first pass with no manifest, `uv run sci-rag build data/raw` ingests the folder, marks every document `unknown` for rights, and builds the graph when a credential is present. Use it for a first spike only. A document is ingested once: a later manifest for the same file is skipped as a duplicate, so its rights and metadata would never be recorded. To start over, remove the documents with `sci-rag corpus delete` and ingest from the manifest.

## Step 2: describe your documents

The manifest, `data/corpus.jsonl`, has one JSON line per document. Citations and rights come from it.

Draft it, then review it:

```bash title="Terminal"
uv run sci-rag draft manifest --folder data/raw
```

The drafter reads each document's opening pages and proposes a title, authors, year, DOI, journal, and a shared source label per document. Review `data/corpus.jsonl.proposed`, then move it into place, or re-run with `--apply`.

Every drafted row says `license_class: unknown`, and the command reports how many documents need a rights decision. Retrieval treats `unknown` as unsafe: those documents stay reachable from your own terminal and drop out of any request that restricts rights. When the drafter finds a license sentence in the document, it quotes the sentence into `license_source` for you to read.

For a handful of documents, write the file by hand:

```jsonl title="data/corpus.jsonl"
{"path": "raw/lee-2021-fouling-review.pdf", "title": "Membrane Fouling Mechanisms: A Review", "authors": ["Lee, S.", "Park, J."], "year": 2021, "doi": "10.1000/example", "license_class": "open_commercial", "source": "journal_papers"}
{"path": "raw/epa-membrane-guidance.pdf", "title": "EPA Membrane Filtration Guidance Manual", "authors": ["US EPA"], "year": 2005, "license_class": "public", "source": "agency_reports"}
{"path": "raw/chen-thesis.pdf", "title": "Chen PhD Thesis", "year": 2023, "license_class": "restricted", "source": "theses"}
```

`path` is relative to the manifest file and is the only required field. `license_class` is one of `public`, `open_commercial`, `open_noncommercial`, `restricted`, or `unknown`; aliases such as `CC-BY` and `cc0` are understood. `source` is your own grouping label and becomes a retrieval filter, so choose 3 to 6 labels. The [configuration reference](configuration.md#datacorpusjsonl) describes every field.

Check the file before you ingest it:

```bash
uv run sci-rag manifest lint data/corpus.jsonl
```

The linter reports every problem at once with line numbers: missing files, paths listed twice, unsupported file types, entries with no title, and misspelled keys the loader would ignore. It is strict about `license_class` because ingestion is not: a mistyped value such as `CC-BY-NC-ND-4.0` is normalized to `unknown` without an error, which removes the document from results you expected it in.

<div class="srag-checkpoint" markdown>
**Checkpoint: the manifest is clean and the rights are decided**

`manifest lint` reports no problems. No row still says `license_class: unknown` unless you meant it to. The count the linter prints is the number of rights decisions still owed.
</div>

## Step 3: name your concepts

`domain/domain.yaml` declares the kinds of things in your field (entity types) and how they relate (relation types). Together these are the ontology. The graph builder extracts only what this file declares. It ships with the demo's agricultural types; replace them with yours.

Draft it from your documents, then edit:

```bash title="Terminal"
uv run sci-rag draft ontology --folder data/raw
```

Review `domain/domain.yaml.proposed`, or re-run with `--apply`. After ingestion, drop `--folder` and the drafter samples the corpus in the database. If you already have an ontology you mostly like, run with `--refine`: the model then proposes only additions and removals, with a reason for each removal. `--cold` drafts from the description alone. The tuned `retrieval:` and `compression:` blocks carry over unchanged in every case.

You will edit this file by hand. Filled in for the worked example:

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

Three rules for choosing well:

- Use 6 to 15 entity types. With fewer, the graph blurs distinct concepts together; with more, extraction becomes inconsistent. Ask what column headings an expert would use to organize a spreadsheet of the field's facts.
- Write each description as a prompt. The extraction model sees it verbatim, and concrete examples in parentheses do more than abstract phrasing.
- Make each relation read as a sentence: "polyamide SUFFERS_FROM chlorine degradation".

Update `query_classes` in the same file: 3 to 5 kinds of question your users ask, each with a few trigger keywords and a one-line instruction for how an answering passage would read. These steer the retrieval layer that writes a hypothetical answer and searches for text that resembles it.

## Step 4: build the knowledge base

One command ingests the manifest and then builds the graph:

```bash
uv run sci-rag build --manifest data/corpus.jsonl
```

Ingestion parses each document, splits it into chunks that keep their section headings and tables intact, embeds the chunks, and stores everything in Postgres. This part runs on any embedding setup, including the offline one.

The graph needs a model. The builder reads every chunk, extracts entities and relationships in your ontology, clusters related entities, and writes a summary of each cluster. Without a credential, `build` says so and stops after ingestion. Vector and keyword retrieval work at that point. The two graph steps are also available on their own, which is how you add the graph later or rebuild it after changing the ontology:

!!! note "Needs a model credential"

    ```bash
    uv run sci-rag graph extract
    uv run sci-rag graph communities
    ```

    Without a credential these exit 1 at the model boundary. Skip them and continue; nothing later in this tutorial depends on the graph except the graph's own checkpoint.

Look at what you have:

```bash
uv run sci-rag stats
uv run sci-rag retrieve "a question in your field" --profile interactive
```

<div class="srag-checkpoint" markdown>
**Checkpoint: the corpus and the graph both look like your field**

`sci-rag stats` after ingest: the chunk count is plausible (a dense 20-page PDF is usually 15 to 40 chunks) and the license classes match what you declared.

`sci-rag retrieve` with a question from your field: the top chunks are recognizable, and the stage table names the layer that found each one.

`sci-rag stats` after the graph built: a 50-document corpus shows entities in the low hundreds. Near zero means the ontology and the corpus do not match, usually because the types are too abstract or the documents too thin. Thousands means the types are too loose. In either case, return to step 3, redraft with `--refine`, and run `graph extract` again.

Offline, the first two readings are the checkpoint. There are no entities to count.
</div>

## Step 5: write seed questions, then measure

`domain/eval_seed_questions.jsonl` needs 10 to 20 questions a domain expert can vouch for. Every retrieval and answer score is computed against them, which makes this the most important manual step in the tutorial.

Draft the first ten, then sign off on each one:

```bash title="Terminal"
uv run sci-rag draft questions --count 10
```

The drafter samples passages from your corpus, asks the model for questions grounded in them, and then verifies in Python that every quoted evidence phrase appears in a passage from a document the question names. Rows that fail are dropped and reported.

Every drafted row carries a `drafted` tag. While any remain, `sci-rag eval retrieval` and `sci-rag eval answers` state in their reports that the ground truth is unreviewed. Read each question, check it against the document it cites, and delete the tag. That deletion is the sign-off; nothing removes the tag for you.

If you already have questions people asked, `uv run sci-rag draft seed-from-answers questions.txt` takes one question per line, answers each, and proposes the reference answer and evidence phrases from what the answer cited. It keeps a phrase only when it appears verbatim in both the answer and the source. These rows arrive tagged `drafted` too.

To add your own, write one JSON object per line:

```jsonl title="domain/eval_seed_questions.jsonl"
{"id": "pfas-rejection", "question": "What PFAS rejection does a polyamide RO membrane achieve?", "reference_answer": "Above 99 percent for long-chain PFAS at typical seawater RO conditions, per Lee 2021.", "reference_titles": ["Membrane Fouling Mechanisms: A Review"], "evidence_phrases": ["99", "long-chain PFAS"], "tags": ["performance"]}
```

Choose evidence phrases distinctive enough that finding them means finding the answer; numbers with units work best. Include one or two questions whose answers span documents. Include one question the corpus cannot answer, tagged `unanswerable`, to check that the system reports the gap. The [configuration reference](configuration.md#domaineval_seed_questionsjsonl) describes every field.

Then measure:

```bash
uv run sci-rag eval retrieval --ablation
```

This runs offline. It scores retrieval against your questions and prints one row per layer configuration, so you can see what each layer contributes on your corpus. Grading generated answers is a second pass and needs a model:

!!! note "Needs a model credential"

    ```bash
    uv run sci-rag eval answers
    ```

Compare every row against `full_deep`, the row with every layer on. If `no_graph` matches `full_deep`, the graph is not contributing yet. That usually points to the ontology, sometimes to a small corpus. Edit the ontology or the corpus, run again, and compare. [Evaluate your pipeline](evaluation.md) explains every column.

## Step 6: adjust the prompts (optional)

The prompts in `domain/prompts/` are short Markdown files. For most fields only two are worth touching:

- `entity_extraction.md`: keep the rules and change the example JSON names to your field, so the model sees the register you expect.
- `answer.md`: add domain-specific answer norms, such as "always report flux in LMH" or "state the test conditions with every rejection value".

A model can reword them for your field while keeping the job identical:

```bash title="Terminal"
uv run sci-rag draft prompts entity_extraction
uv run sci-rag draft prompts answer
```

Every `$SLOT` has to survive, so the rewrite is rendered against dummy values before it is written. These two prompts are the only ones the command touches. The judge prompts, the compression prompt, and the drafting prompt are refused by name, because rewording them would change what the scores mean.

Prompt wording moves every downstream number. Run `sci-rag eval retrieval --ablation` again after a rewrite and compare.

## Step 7: ask, then serve

With a credential, ask a question in your field. Ask one the corpus cannot answer as well; the response should say so.

!!! note "Needs a model credential"

    ```bash
    uv run sci-rag answer "a question in your field"
    ```

Serve the same thing to people and agents:

```bash
uv run sci-rag serve
```

Before anyone else connects, set API keys in `.env` (see `.env.example`) and decide what an outside caller may see. A public or semi-public endpoint should pin callers to `{"license_classes": ["public", "open_commercial"]}` so `restricted` and `unknown` documents stay internal. [REST, MCP, and Python API](api.md) covers keys, scopes, and the agent tools. [Deploy on Google Cloud](deploy-gcp.md) covers Cloud Run.

<div class="srag-checkpoint" markdown>
**Checkpoint: it is your knowledge base now**

Offline, ask a question in your field through `POST /v1/query`. The response names documents you put there, with the license class you declared and the retrieval layer that found each one.

With a credential, the same question through `POST /v1/answer` or `sci-rag answer` returns numbered citations to those documents.
</div>

## Drafting with a model

Three of the steps above draft a file: the manifest, the ontology, and the seed questions. `sci-rag new` and `sci-rag init` can also draft the ontology from a one-sentence description before any document exists; that draft is a first guess to replace in step 3.
Only `sci-rag new` checks the credential with a small live request first. `sci-rag init` uses the key or project you enter as given.

Every drafter offers the same three routes to the same validated file.

=== "Generate it"

    The configured model drafts the file. The reply is validated through the same model the loader uses, so a draft is never something the kit would later refuse to load.

    ```bash title="Terminal"
    uv run sci-rag draft questions --count 10
    ```

=== "Paste it into any assistant"

    No API key and no provider account. `--print-prompt` writes the rendered prompt, including the sampled passages, to standard output. Paste it into the assistant you already use, save the reply, and feed it back.

    ```bash title="Terminal"
    uv run sci-rag draft questions --count 10 --print-prompt > prompt.txt
    # paste prompt.txt into an assistant, save the JSON reply as reply.json
    uv run sci-rag draft questions --count 10 --from-file reply.json
    ```

    Pass the same `--count` and `--folder` values to both commands. They decide which passages are sampled, and the reply is validated against the passages the assistant saw.

=== "Write it yourself"

    Every file format is shown above, and a drafter never touches a hand-written file.

Four rules hold for every drafter:

- Nothing is overwritten. A run writes `<file>.proposed` and prints a summary; moving it into place is your step. `--apply` skips the proposal, and for seed questions it appends, never replaces. `--dry-run` writes nothing.
- Rights are never guessed. Every drafted manifest row says `unknown`.
- Drafted questions stay labeled until a person removes the `drafted` tag. The evaluation reports repeat the label until then.
- `domain/eval_calibration_labels.jsonl` is never drafted. It holds human scores used to check the model grader, and generating it with a model would remove the only independent measurement.

`sci-rag doctor` reports on the domain files beside its usual checks: whether the ontology is large enough to extract against, whether every answerable question cites a document that exists, how many questions still carry the `drafted` tag, and how many manifest rows have no rights decision. Run it after changing anything in `domain/`.

## Offline: what you can prove without a model

The whole route, in order, with nothing that stops at a credential boundary. Set `SCI_RAG_EMBEDDING_PROVIDER=local-hash` in `.env` first.

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

The offline embedder matches on words, not meaning. Treat its retrieval scores as a floor for your corpus, not as a comparison with a credentialed run. This route does not reach the knowledge graph, community summaries, graded answers, or generated cited answers.

## The improvement loop

Corpus and ontology changes are cheap, and the evaluation reports tell you whether a change helped. Add or fix a handful of documents, run `build` again (it processes only what is new), run the two eval commands, and read the diffs. When a user asks a question the system misses, add it as a seed question first, then fix the miss.

## Next steps

- Read the evaluation table before you change a retrieval setting: [Evaluate your pipeline](evaluation.md)
- Grow the corpus from a topic or a DOI list: [Run a corpus campaign](campaigns.md)
- See what a license class does to retrieval: [Scope precedes ranking](methodology.md#7-scope-precedes-ranking)
- Put the service where your group can reach it: [Deploy on Google Cloud](deploy-gcp.md)
