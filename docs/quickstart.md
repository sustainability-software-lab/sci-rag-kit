---
title: Quickstart
description: Set up Sci RAG Kit, ingest the synthetic demo corpus, inspect retrieval, produce a cited answer, and serve REST and MCP.
---

# Quickstart

Set up a served, agent-accessible knowledge base over the bundled demo corpus. You will see the evidence returned by each retrieval stage before you add your own literature.

<div class="srag-meta-strip">
  <div><strong>You'll build</strong>A served knowledge base over the demo corpus</div>
  <div><strong>You'll need</strong>Python, pipx, uv, and a PostgreSQL backend</div>
  <div><strong>Time</strong>About 10 minutes</div>
  <div><strong>Credentials</strong>Optional</div>
  <div><strong>Tested with</strong>v0.3</div>
</div>

Run the wizard from the directory where you keep projects. After it creates the repository, run the remaining commands from that repository's root.

## Before you start

| Requirement | Why it is needed | Check |
|---|---|---|
| Python 3.11 or 3.12 | Supported runtime | `python --version` |
| [pipx](https://pipx.pypa.io/) | Isolated install for the project wizard | `pipx --version` |
| [uv](https://docs.astral.sh/uv/) | Environment and dependency management | `uv --version` |
| PostgreSQL backend | Docker, local PostgreSQL, or Cloud SQL with pgvector | See [step 3](#3-install-the-project-and-create-the-schema) |
| Google credential, optional | Real semantic embeddings, graph extraction, and answers | AI Studio key or Vertex ADC |

No Docker? [Run Postgres your way](run-postgres.md) covers conda-forge, a system server such as Postgres.app, and the opt-in Cloud SQL development backend. Step 3 says which one is yours.

## 1. Create the project

### The wizard

For your own project, run the wizard from whatever directory you keep projects in.
It writes a configured, git-initialized project directory:

```console title="Terminal"
$ pipx install sci-rag-kit
$ sci-rag new
```

Choose Quick for six setup decisions, plus the credential value required by the
selected mode, and defaults for the rest. Those decisions cover the project name,
description, contact email, environment manager, credential mode, and corpus source.
Choose Offline explicitly when you do not want a model credential. Choose Advanced
when you need to set models, ontology behavior, parsing, reranking, infrastructure,
demo content, licensing, or Git initialization yourself.

In a supported terminal the menus use arrow keys, show explanations and recommended
choices, and keep API-key input masked. The environment-manager menu preselects the
first supported environment manager found on `PATH`; that convenience does not change
`--defaults` or an answers file. If `SCI_RAG_GOOGLE_API_KEY` or `GOOGLE_API_KEY` is
already set, interactive setup offers to reuse it without displaying its value. Pass
`--no-tty` to force plain numbered prompts.

The credential check runs before the template download, and a failed check gives you
recovery choices without discarding your answers. Continue at step 3 after the wizard
finishes; use step 2 when you need to change the credential mode it wrote.
[Troubleshooting](troubleshooting.md) covers terminal fallback and the credential-check
escape hatch.

### Other ways in

If you want to inspect the kit before creating a project, clone it and run the demo:

```console title="Terminal"
$ git clone https://github.com/sustainability-software-lab/sci-rag-kit.git
$ cd sci-rag-kit
```

The other secondary routes start from the same repository tree:

- GitHub's **Use this template** button creates a repository under your account.
- `sci-rag init` configures a checkout you already have. It shares the Quick and
  Advanced choices and completion report, but does not run the new-project credential
  check.
- The included dev container installs the project and starts Postgres. In GitHub Codespaces, continue at step 2 after it opens.

## 2. Choose a credential mode

The wizard already created `.env` with owner-only mode `0600`; keep it out of
Git. If you used a clone or the GitHub template, create the same file yourself.
Both commands matter: `cp` inherits the public example's mode, so without the
`chmod` every account on the machine can read the key you are about to paste in.

```console
$ cp .env.example .env
$ chmod 600 .env
```

Pick exactly one. **Start with AI Studio** unless your organization already runs on Google Cloud, in which case use Vertex. Offline mode is for machines that cannot reach a model at all, and it costs you the graph and every generated answer.

### AI Studio: start here

One key, no cloud project, real embeddings and real answers. Create an API key at [Google AI Studio](https://aistudio.google.com/apikey), then set:

```dotenv title="~/.env"
SCI_RAG_GOOGLE_API_KEY=your-key-here
```

### Vertex AI: if your lab is already on Google Cloud

Same models, billed through your existing project, no key to hand around. Authenticate Application Default Credentials once, then set the project:

```console
$ gcloud auth application-default login
```

```dotenv title="~/.env"
SCI_RAG_GCP_PROJECT=your-project-id
```

### Offline: when no model is reachable

Use the deterministic local embedder:

```dotenv title="~/.env"
SCI_RAG_EMBEDDING_PROVIDER=local-hash
```

This mode exercises parsing, chunking, storage, ranking, and retrieval evaluation without network calls. Its similarity is lexical, which is a real quality difference. Graph extraction, HyDE, community summaries, generated answers, and model-based judging remain unavailable until you add a model credential.

## 3. Install the project and create the schema

```console title="Terminal"
$ make setup
```

`make setup` starts the selected database backend, installs dependencies, and
applies every migration. Docker is the template default and listens on host
port `5433`; generated projects may select a different supported backend.

If port `5433` is already taken, usually by another Sci RAG Kit project whose
database is running, publish a free one: change the `ports` entry in
`docker-compose.yml` to `"5434:5432"` and set the same port in
`SCI_RAG_DATABASE_URL`. [Troubleshooting](troubleshooting.md#docker) has the
full recovery.

**Expected output**

```text
Database schema is up to date.
```

No Docker? Supported servers are **PostgreSQL 16 through 18**. pixi and conda projects can run one from conda-forge, every environment manager can use a supported system server, and generated projects can opt into a shared Cloud SQL development instance. [Run Postgres your way](run-postgres.md) has all three paths.

<div class="srag-checkpoint" markdown>
**Checkpoint: the foundation is healthy**

Run `uv run sci-rag doctor`. Configuration, domain, database, and schema should report healthy. An empty corpus or missing optional credential can still be informational at this point.
</div>

## 4. Ingest the demo corpus and inspect what came back

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

The demo answer is approximately 302,000 dry tons and cites the synthetic resource assessment. Check the cited passage. The number alone is not success.

In offline mode this command reports that no LLM is configured. That refusal is expected: the system does not fabricate an answer when generation is unavailable.

## 6. Build the graph and run the deep path

With a Google credential:

```console
$ make demo-cloud
```

The target extracts ontology-constrained entities and relationships, builds community summaries, asks a multi-document question, and runs the per-layer retrieval ablation. Reports are written under `eval_results/`.

<div class="srag-checkpoint" markdown>
**Checkpoint: complexity produced evidence**

Open the newest retrieval report. It should identify the corpus fingerprint, models, profile, enabled layers, metrics, confidence intervals, and per-question records. Do not enable an expensive layer in your own profile merely because it worked on this fixture.
</div>

## 7. Serve it to humans and agents

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

Ask the agent to use `demo-corpus` for a question. You should see a `search_corpus` or `answer_question` tool call. An answer from the agent's own memory means the tool never fired.

<div class="srag-checkpoint" markdown>
**Checkpoint: one database, two front doors**

You have one Postgres database holding source records, structure-aware chunks, dense vectors, full-text search, and, if you ran step 6, a concept graph and community summaries. One service serves the same retrieval and answer behavior to the CLI, to REST clients, and to MCP agents, and the reports under `eval_results/` record what it did on known questions.
</div>

## Next steps

**Replace the fixture with your own field.** That is what the kit is for, and the shortest route is [LLM-assisted setup](llm-assisted-setup.md), which drafts the domain files from your own documents. Its copy-paste workflow needs no model credentials. [Bring your own domain](bring-your-own-domain.md) is the same work laid out end to end.

- Something did not match this page: [Troubleshooting](troubleshooting.md)
- Follow ownership through the code: [Architecture](architecture.md)
- Put the service somewhere other people can reach: [Deploy on Google Cloud](deploy-gcp.md)
