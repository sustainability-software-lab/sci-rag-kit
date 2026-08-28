---
title: Quickstart
description: Set up Sci RAG Kit, ingest the synthetic demo corpus, inspect retrieval, produce a cited answer, and serve REST and MCP.
---

# Quickstart

Set up a served, agent-accessible knowledge base over the bundled demo corpus. You will see the evidence returned by each retrieval stage before you add your own literature.

<div class="srag-meta-strip">
  <div><strong>Level</strong>Beginner</div>
  <div><strong>Time</strong>About 10 minutes</div>
  <div><strong>Services</strong>Docker + Postgres</div>
  <div><strong>Credentials</strong>Optional</div>
  <div><strong>Tested with</strong>v0.2</div>
</div>

Every command runs from the repository root.

## Before you start

| Requirement | Why it is needed | Check |
|---|---|---|
| Python 3.11 or 3.12 | Supported runtime | `python --version` |
| [uv](https://docs.astral.sh/uv/) | Environment and dependency management | `uv --version` |
| Docker | Local Postgres with pgvector | `docker version` |
| Google credential, optional | Real semantic embeddings, graph extraction, and answers | AI Studio key or Vertex ADC |

No Docker? Two of the four environment managers can run Postgres without it. [Run Postgres your way](run-postgres.md) covers all three paths.

## 1. Get the repository

For your own project, run the wizard from whatever directory you keep projects in. It asks about your domain, credentials, ontology, corpus, and environment manager, then writes a configured, git-initialized project directory:

```console title="Terminal"
$ pipx install sci-rag-kit
$ sci-rag-new
```

Every question has a default, so you can press Enter through the whole session and still get a project that runs. Steps 2 and 3 below are the questions it asked; read them to understand what it wrote, then skip to step 4.

Evaluating the kit rather than starting a project? Clone it:

```console title="Terminal"
$ git clone https://github.com/sustainability-software-lab/sci-rag-kit.git
$ cd sci-rag-kit
```

Clicking **Use this template** on GitHub also works. Inside a checkout you already have, `sci-rag init` runs the same wizard. The included dev container is another supported path. In GitHub Codespaces it installs the project and starts Postgres, so continue with configuration.

## 2. Choose a credential mode

Create the local environment file:

```console
$ cp .env.example .env
```

Choose exactly one mode.

### AI Studio: fastest real model

Create an API key at [Google AI Studio](https://aistudio.google.com/apikey), then set:

```dotenv title="~/.env"
SCI_RAG_GOOGLE_API_KEY=your-key-here
```

### Vertex AI: labs & Google Cloud

Authenticate Application Default Credentials once, then set the project:

```console
$ gcloud auth application-default login
```

```dotenv title="~/.env"
SCI_RAG_GCP_PROJECT=your-project-id
```

### Offline: no credentials

Use the deterministic local embedder:

```dotenv title="~/.env"
SCI_RAG_EMBEDDING_PROVIDER=local-hash
```

This mode exercises parsing, chunking, storage, ranking, and retrieval evaluation without network calls. Its similarity is lexical rather than semantic. Graph extraction, HyDE, community summaries, generated answers, and model-based judging remain unavailable until you add a model credential.

## 3. Install the project and create the schema

```console title="Terminal"
$ make setup
```

That installs dependencies, starts the compose Postgres on host port `5433`, and applies every migration.

**Expected output**

```text
Database schema is up to date.
```

No Docker? Supported servers are **PostgreSQL 16 through 18**, and there are two other ways to get one. pixi and conda projects run theirs from conda-forge with the same `make setup`; uv and venv projects point at a server you already have. [Run Postgres your way](run-postgres.md) has both.

<div class="srag-checkpoint" markdown>
**Checkpoint: the foundation is healthy**

Run `uv run sci-rag doctor`. Configuration, domain, database, and schema should report healthy. An empty corpus or missing optional credential can still be informational at this point.
</div>

## 4. Ingest & inspect the demo

```console
$ make demo
```

This command ingests five synthetic CC0 documents about agricultural residues, retrieves evidence for one question, and scores retrieval against the bundled seed questions. The numbers are plausible but fictional; the fixture demonstrates the pipeline, not the state of a real region.

**Expected output**

```text
Ingestion report
5 ingested, 0 skipped, 0 failed.

vector     success     ...
keyword    success     ...
graph      disabled    ...
```

Exact candidate counts and metric values depend on the credential mode. `graph disabled` is normal here because `make demo` uses the interactive profile, which intentionally leaves the model-dependent graph layer off.

<div class="srag-checkpoint" markdown>
**Checkpoint: evidence is inspectable**

The retrieval table should show a title, section path, license class, contributing layers, fused score, and content excerpt. The stage table should distinguish success, empty, disabled, or failure rather than silently omitting a layer.
</div>

## 5. Generate a cited answer

With a Google credential:

```console
$ uv run sci-rag answer "How much rice straw was generated in the Colusa Basin in 2023?"
```

The demo answer is approximately 302,000 dry tons and cites the synthetic resource assessment. Check the cited passage rather than treating the number alone as success.

In offline mode this command reports that no LLM is configured. That refusal is expected: the system does not fabricate an answer when generation is unavailable.

## 6. Build the graph & deep path

With a Google credential:

```console
$ make demo-cloud
```

The target extracts ontology-constrained entities and relationships, builds community summaries, asks a multi-document question, and runs the per-layer retrieval ablation. Reports are written under `eval_results/`.

<div class="srag-checkpoint" markdown>
**Checkpoint: complexity produced evidence**

Open the newest retrieval report. It should identify the corpus fingerprint, models, profile, enabled layers, metrics, confidence intervals, and per-question records. Do not enable an expensive layer in your own profile merely because it worked on this fixture.
</div>

## 7. Serve humans & agents

```console
$ uv run sci-rag serve
```

The one process exposes:

- OpenAPI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Corpus manifest: [http://127.0.0.1:8000/v1/corpus-manifest](http://127.0.0.1:8000/v1/corpus-manifest)
- MCP over streamable HTTP: `http://127.0.0.1:8000/mcp`

Try retrieval through REST:

```console
$ curl -s -X POST http://127.0.0.1:8000/v1/query \
    -H 'Content-Type: application/json' \
    -d '{"query": "rice straw availability", "top_k": 3}'
```

For a local agent over stdio:

```console
$ claude mcp add demo-corpus -- uv run --directory "$(pwd)" sci-rag mcp
```

Ask the agent to use `demo-corpus` for a question. You should see a `search_corpus` or `answer_question` tool call rather than an answer from the agent's unaided memory.

## What you built

You now have one Postgres database containing source records, structure-aware chunks, dense vectors, full-text search, and, if enabled, a concept graph and community summaries. One service exposes the same retrieval and answer behavior to CLI users, REST clients, and MCP agents. The evaluation artifacts record what that system did on known questions.

## Continue

Ready to replace the fixture with your own field? Start with
[LLM-assisted setup](llm-assisted-setup.md) to draft the domain files from
your documents. Its copy-paste workflow needs no model credentials.

- Replace the fixture with your field: [Bring your own domain](bring-your-own-domain.md)
- Follow ownership through the code: [Architecture](architecture.md)
- Understand provenance and license scope: [Evidence and rights](evidence-and-rights.md)
- Diagnose a mismatch: [Troubleshooting](troubleshooting.md)
- Enrich DOI metadata and review known retractions: [Operations](operations.md#crossref-enrichment-and-retraction-review)
- Deploy the service: [Google Cloud guide](deploy-gcp.md)
