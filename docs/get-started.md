---
title: Get started
description: Install Sci RAG Kit, run the demo corpus, then bring in a corpus of your own.
---

# Get started

Install with `pipx install sci-rag-kit`, then run `sci-rag new`. The three pages below take that project from an empty database to a knowledge base over a corpus of your own. The first reaches a working demo in about ten minutes. The second replaces the demo with your documents. The third is where to go when a step fails.

<div class="srag-rows" markdown>

[<span class="srag-row__title">Quickstart</span><span class="srag-row__copy">Create a project, start the database, ingest the demo corpus, ask a question, and serve the result. About ten minutes.</span>](quickstart.md){ .srag-row }

[<span class="srag-row__title">Bring your own domain</span><span class="srag-row__copy">Seven commands from a folder of documents to a knowledge base that answers questions about them.</span>](bring-your-own-domain.md){ .srag-row }

[<span class="srag-row__title">Troubleshooting</span><span class="srag-row__copy">Start from the symptom, run `sci-rag doctor`, and follow the fix.</span>](troubleshooting.md){ .srag-row }

</div>

## What the kit sets up

A knowledge base built with the kit is one Postgres database and one small service. Documents go in as passages, each carrying a vector for search by meaning, an entry in the full-text index for search by exact words, and links into a graph of the concepts it mentions. Questions come out with numbered citations to the passages the answer used. One service answers the command line, a REST API, and agents over MCP. MCP is the Model Context Protocol: tools such as Claude Code call the corpus the same way a person at the terminal does.

The wizard asks for six setup decisions and the credential value that mode needs. It is fine to choose Offline: ingestion, retrieval, and retrieval scoring work without a model, and the graph and generated answers switch on when a credential is added later. The generator configures the live template in place, so the resulting project is the same tree that is readable on GitHub, with nothing left as a placeholder.

## Where things live

A new field is configured in `domain/` and `data/`, not by editing Python. The layout below is what `sci-rag new` produces.

<div class="srag-tree">your-project/
├── domain/                  the field
│   ├── domain.yaml          the concepts and relationships the graph looks for
│   ├── prompts/             the wording sent to the model, one file per job
│   └── eval_seed_questions.jsonl   questions with known answers, for scoring
├── data/
│   ├── raw/                 the source documents
│   ├── corpus.jsonl         one line per document: title, authors, rights
│   └── demo/                five synthetic documents, so the pipeline runs on day one
├── .env                     credentials, database URL, model names
├── src/sci_rag/             the pipeline; rarely opened in a normal project
├── migrations/              database tables, applied by make setup
├── tests/                   runs offline; database tests use a disposable database
├── infra/terraform/         optional Google Cloud deployment
└── docs/                    this site</div>

`domain/domain.yaml` is the file most projects edit most. It names the kinds of things in the field (entity types such as `Membrane` or `Contaminant`) and how they relate (`REMOVES`, `SUFFERS_FROM`). The graph builder extracts only what this file declares, so a vague ontology produces a thin graph and a precise one produces a useful one. `data/corpus.jsonl` records, for each document, the metadata a citation needs and whether the text may be redistributed. `domain/eval_seed_questions.jsonl` holds the questions every score is computed against. Ten good ones an expert will vouch for are worth more than a hundred vague ones.

[Architecture](architecture.md) explains what each package under `src/sci_rag/` owns, for projects that change the pipeline itself.

## Recommended path

1. Run the [quickstart](quickstart.md). Offline mode gives a credential-free first pass; AI Studio gives the full result.
2. Follow [Bring your own domain](bring-your-own-domain.md) with 20 to 50 well-understood documents. The drafting commands write the first version of every domain file.
3. Run [Evaluate your pipeline](evaluation.md) before changing any retrieval setting. Its table shows what each retrieval layer contributes on the corpus at hand.
4. When the corpus should grow beyond what is on disk, [Run a corpus campaign](campaigns.md) finds papers by topic or DOI list and checks their rights.

Still deciding whether this is the right tool? The [FAQ](faq.md) and [Choosing Sci RAG Kit](choosing-sci-rag-kit.md) answer that. When Postgres, credentials, or parsing get in the way, `uv run sci-rag doctor` names the layer that is missing; run it before guessing.
