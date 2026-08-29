---
title: Tour the repository
description: Learn which Sci RAG Kit files define your scientific domain, which implement the pipeline, and what runs in production.
---

# Tour the repository

By the end of this page you can point at the file that owns each part of the system: your science, your documents, the pipeline, and what runs in production. Sci RAG Kit is a working GitHub template repository, so your copy holds the application, its domain profile, its tests, and its operations code in one place.

<div class="srag-meta-strip">
  <div><strong>You'll build</strong>A map of what you own and what you run</div>
  <div><strong>You'll need</strong>A checkout, open in an editor</div>
  <div><strong>Time</strong>About 10 minutes</div>
  <div><strong>Tested with</strong>v0.3</div>
</div>

## Before you start

| Requirement | Why | Check |
|---|---|---|
| A checkout of the kit, or a generated project | Every path below is one you can open | `ls domain src/sci_rag` |
| Nothing else | No database, no credentials, no install | |

Reading is enough. Nothing on this page changes a file.

## Three contexts, one repository

Use these terms consistently when reading the docs:

| Context | What it means | Typical action |
|---|---|---|
| **Upstream template** | The Sustainability Software Lab repository before you create your copy | Evaluate the method, read changes, pull improvements |
| **Your repository** | The copy your team owns and configures | Edit `domain/`, add corpus manifests, run tests, deploy |
| **Runtime system** | The Postgres database and Sci-RAG service created from your repository | Ingest, retrieve, answer, evaluate, serve REST and MCP |

There is no separate template-definition tree. `sci-rag new` fetches the live
tree at the release tag and configures a new project in place. Clicking **Use
this template** copies the same tree, while `sci-rag init` configures a checkout
you already have. `scripts/init_domain.py` remains the narrow route for changing
project-facing names and resetting the domain seed material.

!!! why "Why a live template?"
    The template itself remains executable and testable. A maintainer can validate a change against the same files a new project receives, without maintaining a second layer of placeholder-filled source.

## The map

<div class="srag-tree">sci-rag-kit/
├── domain/                  ontology, prompts, retrieval tuning, eval questions
│   ├── domain.yaml          the validated scientific profile
│   ├── prompts/             extraction, answer, HyDE, judge, and rerank prompts
│   └── eval_seed_questions.jsonl
├── data/
│   ├── demo/                five synthetic CC0 documents and their manifest
│   └── raw/                 the conventional home for your source files
├── src/sci_rag/
│   ├── ingest/              parse, chunk, manifest, deduplicate, store
│   ├── campaigns/           discovery, explicit OA rights, verified PDF downloads
│   ├── embed/               Google and deterministic offline embeddings
│   ├── graph/               entity extraction and community summaries
│   ├── retrieve/            five stages, routing, fusion, and reranking
│   ├── answer/              grounded generation and citation events
│   ├── evals/               retrieval, answer, statistics, judge, and reports
│   ├── server/              shared service, REST routers, MCP, and auth
│   ├── cli/                 the `sci-rag` command surface
│   └── enrich.py            Crossref metadata and retraction assertions
├── migrations/              Alembic history for Postgres and pgvector
├── tests/                   offline unit, integration, server, and smoke evidence
├── examples/                runnable library and notebook entry points (optional)
├── infra/terraform/         optional Cloud SQL and Cloud Run deployment
├── docs/                    this site, methodology, guides, and decisions
├── docker-compose.yml       local Postgres with pgvector
└── Makefile                 readable shortcuts over the real commands</div>

Entries marked optional are choices in Advanced setup. Quick keeps production
Terraform and the demo corpus, and leaves the Cloud SQL development helper out.
Use `sci-rag new --advanced` for a new project, or `sci-rag init --advanced` in
a checkout, when you want to change those defaults. If you answer no to
`include_terraform` or `include_demo_corpus`, the files are removed and neither
the `Makefile` nor CI mentions them.

## What you change

Most teams begin with four changes:

1. Put documents under `data/` and describe each source in a JSONL manifest.
2. Replace the entity types, relationship types, query classes, and retrieval tuning in `domain/domain.yaml`.
3. Adjust `domain/prompts/*.md` for the language and evidence conventions of the field.
4. Replace `domain/eval_seed_questions.jsonl` with questions whose evidence your team can verify.

The [Bring your own domain](bring-your-own-domain.md) guide works through those changes. Do not edit retrieval weights simply because a different number looks plausible. Run the [ablation workflow](evaluation.md) and keep the change only if it earns its place on your corpus.

## Where a change belongs

| You want to change | Start here | Keep invariant |
|---|---|---|
| Scientific concepts and relations | `domain/domain.yaml` | Valid entity and relation names |
| How the model extracts or answers | `domain/prompts/` | Required `$SLOTS` and citation contract |
| Which documents enter the corpus | Manifest JSONL or a `CorpusEntry` collector | Source, rights, and identity metadata |
| Which works to review and download | `sci-rag campaign discover` / `build` | Resumable state, explicit rights, and verified direct PDFs |
| A file format | `src/sci_rag/ingest/parsers.py` | The shared `ParsedDocument` block model |
| Model provider | `EmbeddingProvider` or `LLMClient` | Dimensions, version stamps, async behavior |
| Ranking behavior | `src/sci_rag/retrieve/` | Scope before ranking, traces, and ablation evidence |
| External interface | `RagService` first, then REST/MCP adapter | One behavior behind both front doors |

## From checkout to runtime

`make setup` installs the project, starts Postgres, and applies migrations. Ingestion turns a manifest entry into document and chunk rows. Optional graph building adds concepts, edges, and community summaries. Retrieval reads those rows through scoped layers. Answer generation formats the returned items as numbered sources. Evaluation stamps reports with the corpus fingerprint, models, configuration, and Git commit.

<div class="srag-checkpoint" markdown>
**Orientation checkpoint**

You should now be able to point to the file that owns each of these four things. Scientific vocabulary lives in `domain/domain.yaml`, source rights in the manifest JSONL, runtime defaults in `src/sci_rag/config.py` or `.env`, and measured quality in `domain/eval_seed_questions.jsonl` plus `eval_results/`.
</div>

## Next steps

- Put a running database behind the map: [Quickstart](quickstart.md)
- Replace the demo profile with your field: [Bring your own domain](bring-your-own-domain.md)
- See why the tree is shaped this way: [Architecture](architecture.md)
