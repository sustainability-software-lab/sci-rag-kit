---
title: Get started
description: Install Sci RAG Kit, run the demo corpus, then put your own documents in.
---

# Get started

Install the kit with `pipx install sci-rag-kit` and run `sci-rag new`. Then follow the three pages below in order. The first gives you a working knowledge base over a demo corpus in about ten minutes. The second replaces the demo with your own documents. The third is where to go when a step fails or shows something other than what the page describes.

<div class="srag-rows" markdown>

[<span class="srag-row__title">Quickstart</span><span class="srag-row__copy">Create a project, start the database, ingest the demo corpus, ask a question, and serve the result. About ten minutes.</span>](quickstart.md){ .srag-row }

[<span class="srag-row__title">Bring your own domain</span><span class="srag-row__copy">Seven commands from a folder of documents to a knowledge base that answers questions about them.</span>](bring-your-own-domain.md){ .srag-row }

[<span class="srag-row__title">Troubleshooting</span><span class="srag-row__copy">Start from the symptom, run `sci-rag doctor`, and follow the fix.</span>](troubleshooting.md){ .srag-row }

</div>

## What you are setting up

A knowledge base is one Postgres database and one small service. Your documents go in as passages, each with a vector, a full-text index entry, and links into a graph of the concepts it mentions. Questions come out with numbered citations to the passages the answer used. The same service answers the command line, a REST API, and agents over MCP. MCP is the Model Context Protocol, the way tools such as Claude Code call external systems.

The wizard asks for six setup decisions and the credential value that decision needs. You can choose Offline when you do not want a model credential yet. Ingestion, retrieval, and retrieval scoring work without one. The graph and generated answers switch on when you add a credential later. The generator configures the live template in place, so the project you get is the tree you can read on GitHub, with your answers written into its configuration files.

## Where things live

Everything specific to your field sits in two folders you edit and one file you fill in. Pointing the kit at a new field never means editing Python.

<div class="srag-tree">your-project/
├── domain/                  your field
│   ├── domain.yaml          the concepts and relationships the graph looks for
│   ├── prompts/             the wording sent to the model, one file per job
│   └── eval_seed_questions.jsonl   questions with known answers, for scoring
├── data/
│   ├── raw/                 your source documents
│   ├── corpus.jsonl         one line per document: title, authors, rights
│   └── demo/                five synthetic documents, so the pipeline runs on day one
├── .env                     credentials, database URL, model names
├── src/sci_rag/             the pipeline; you rarely need to open it
├── migrations/              database tables, applied by make setup
├── tests/                   runs offline; database tests use a disposable database
├── infra/terraform/         optional Google Cloud deployment
└── docs/                    this site</div>

`domain/domain.yaml` is the file you will edit most. It names the kinds of things in your field (entity types such as `Membrane` or `Contaminant`) and how they relate (`REMOVES`, `SUFFERS_FROM`). The graph builder extracts only what this file declares. `data/corpus.jsonl` records, per document, the metadata a citation needs and whether the text may be redistributed. `domain/eval_seed_questions.jsonl` holds the questions every score is computed against.

[Architecture](architecture.md) explains what each package under `src/sci_rag/` owns, for when you want to change the pipeline rather than configure it.

## Recommended path

1. Run the [quickstart](quickstart.md). Choose Offline for a credential-free first pass, or AI Studio for the full result.
2. Follow [Bring your own domain](bring-your-own-domain.md) with 20 to 50 documents you know well. The drafting commands write the first version of every domain file for you.
3. Run [Evaluate your pipeline](evaluation.md) before you change any retrieval setting. Its table shows what each retrieval layer contributes on your corpus.
4. When the corpus should grow beyond what you have on disk, [Run a corpus campaign](campaigns.md) finds papers by topic or DOI list and checks their rights.

Still deciding whether this is the right tool? Read the [FAQ](faq.md), then [Choosing Sci RAG Kit](choosing-sci-rag-kit.md). When Postgres, credentials, or parsing get in the way, run `uv run sci-rag doctor` before guessing. It names the layer that is missing.
