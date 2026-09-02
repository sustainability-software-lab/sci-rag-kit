---
title: Get started
description: Install Sci RAG Kit, run the demo corpus, then put your own documents in, in that order.
---

# Get started

Install the kit with `pipx install sci-rag-kit`, run `sci-rag new`, and follow the three pages below in order. The first gives you a working knowledge base over a demo corpus in about ten minutes. The second replaces the demo with your own documents. The third is where to go when something does not match.

<div class="srag-rows" markdown>

[<span class="srag-row__title">Quickstart</span><span class="srag-row__copy">Create a project, start the database, ingest the demo corpus, ask a question, and serve the result to people and agents. About 10 minutes.</span>](quickstart.md){ .srag-row }

[<span class="srag-row__title">Bring your own domain</span><span class="srag-row__copy">Seven commands from a folder of PDFs to a knowledge base that answers questions about them, with your concepts in the graph and your questions scoring it.</span>](bring-your-own-domain.md){ .srag-row }

[<span class="srag-row__title">Troubleshooting</span><span class="srag-row__copy">Start from the symptom, run `sci-rag doctor`, and follow the specific check or recovery path.</span>](troubleshooting.md){ .srag-row }

</div>

## What you are setting up

A knowledge base is one Postgres database plus one small service. Your documents go in as chunks with their embeddings, full-text index, and a graph of the concepts they mention. Questions come out with numbered citations back to the passages the answer used. The same service answers the command line, a REST API, and agents over MCP (Model Context Protocol, the way tools such as Claude Code call out to external systems).

The wizard asks for six setup decisions and the credential value that decision needs. You can choose Offline when you do not want a model credential yet: ingestion, retrieval, and retrieval scoring all work without one, and the graph and generated answers switch on when you add a credential later. The generator configures the live template in place, so the project you get is the same tree you can read on GitHub, with your answers written into its configuration files.

## Where things live

Everything specific to your field sits in two folders you edit and one file you fill in:

<div class="srag-tree">your-project/
├── domain/                  your field: concepts, prompts, test questions
│   ├── domain.yaml          the concepts and relationships the graph looks for
│   ├── prompts/             the wording sent to the model, one file per job
│   └── eval_seed_questions.jsonl   questions with known answers, for scoring
├── data/
│   ├── raw/                 your source documents
│   ├── corpus.jsonl         one line per document: title, authors, rights
│   └── demo/                five synthetic documents, so the pipeline runs on day one
├── .env                     credentials, database URL, model names
├── src/sci_rag/             the pipeline itself; you rarely need to open it
├── migrations/              database tables, applied by make setup
├── tests/                   runs offline; database tests use a disposable database
├── infra/terraform/         optional Google Cloud deployment
└── docs/                    this site</div>

The split is deliberate: pointing the kit at a new field never means editing Python. [Architecture](architecture.md) explains what each package under `src/sci_rag/` owns, for when you want to change the pipeline rather than configure it.

## Recommended path

1. Run the [quickstart](quickstart.md). Choose Offline if you want a credential-free first pass; choose AI Studio for the full result.
2. Follow [Bring your own domain](bring-your-own-domain.md) with 20 to 50 documents you know well. The drafting commands write the first version of every domain file for you.
3. Run [Evaluate your pipeline](evaluation.md) before you change any retrieval setting. The table it prints tells you what each retrieval layer contributes on your corpus.
4. When the corpus should grow beyond what you have on disk, [Run a corpus campaign](campaigns.md) finds papers by topic or DOI list and checks their rights.

Still deciding whether this is the right tool? Read the [FAQ](faq.md) first, then [Choosing Sci RAG Kit](choosing-sci-rag-kit.md). If Postgres, credentials, or parsing get in the way, do not guess from an empty result: run `uv run sci-rag doctor`, which names the layer that is missing.
