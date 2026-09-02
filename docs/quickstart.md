---
title: Quickstart
description: Create a project, start the database, ingest the demo corpus, ask a question, and serve the result to people and agents.
---

# Quickstart

By the end of this page you have a working knowledge base over a small demo corpus: documents in a database, a question answered with citations, and the same thing served to a REST client and to an agent. Everything you do here you will do again with your own documents.

<div class="srag-meta-strip">
  <div><strong>You'll build</strong>A served knowledge base over the demo corpus</div>
  <div><strong>You'll need</strong>Python, pipx, uv, and a way to run PostgreSQL</div>
  <div><strong>Time</strong>About 10 minutes</div>
  <div><strong>Credentials</strong>Optional, but the answer step needs one</div>
  <div><strong>Tested with</strong>v0.4</div>
</div>

## Before you start

| Requirement | Why | Check |
|---|---|---|
| Python 3.11 or 3.12 | The supported runtime | `python --version` |
| [pipx](https://pipx.pypa.io/) | Installs the project wizard in its own environment | `pipx --version` |
| [uv](https://docs.astral.sh/uv/) | Installs the project's dependencies and runs its commands | `uv --version` |
| Docker, or a PostgreSQL 16 through 18 server with pgvector | The database everything lives in | `docker --version` |
| A Google AI Studio key, optional | Real embeddings, the graph, and generated answers | [Create one](https://aistudio.google.com/apikey) |

No Docker? [Run Postgres your way](run-postgres.md) covers a conda-forge server, a system server such as Postgres.app, and the optional Cloud SQL development helper. Step 3 tells you where that choice matters.

## 1. Create the project

### The wizard

Run the wizard from the directory where you keep projects. It writes a configured, git-initialized project directory:

```console title="Terminal"
$ pipx install sci-rag-kit
$ sci-rag new
```

Choose **Quick**. It asks for six setup decisions (project name, a one-line description, contact email, environment manager, credential mode, and where your first documents will come from), plus the credential value the selected mode needs, and supplies defaults for everything else. Choose **Offline** as the credential mode when you do not want a model credential yet. Choose **Advanced** only when you need to set models, parsing, reranking, infrastructure, or licensing yourself.

Two conveniences worth knowing. The environment-manager menu preselects the first supported environment manager found on `PATH`; that does not change what `--defaults` or an answers file would choose. If `SCI_RAG_GOOGLE_API_KEY` or `GOOGLE_API_KEY` is already set in your shell, the wizard offers to reuse it without displaying its value, and any key you type is masked. Pass `--no-tty` for plain numbered prompts.

The wizard checks the credential with one small model request before it downloads the template, and a failed check offers recovery choices without discarding your answers. When it finishes, `cd` into the new directory and continue at step 3. Step 2 is for when you need to change the credential mode it wrote.

### Other ways in

If you want to read the kit before creating a project, clone it and run the demo from the clone:

```console title="Terminal"
$ git clone https://github.com/sustainability-software-lab/sci-rag-kit.git
$ cd sci-rag-kit
```

The other routes start from the same repository tree:

- GitHub's **Use this template** button creates a repository under your account.
- `sci-rag init` configures a checkout you already have. It asks the same Quick or Advanced questions but does not run the credential check.
- The included dev container installs the project and starts Postgres. In GitHub Codespaces, continue at step 2 after it opens.

## 2. Choose a credential mode

The wizard already created `.env` with owner-only mode `0600` and wrote your choice into it; skip to step 3 unless you want to change it. From a clone or the GitHub template, create the file yourself. Both commands matter: `cp` inherits the public example's mode, so without the `chmod` every account on the machine can read the key you are about to paste in.

```console
$ cp .env.example .env
$ chmod 600 .env
```

Then pick exactly one of these. **AI Studio** is the right choice for almost everyone.

=== "AI Studio"

    One key, no cloud project, real embeddings and real answers. Create a key at [Google AI Studio](https://aistudio.google.com/apikey), then set:

    ```dotenv title="~/.env"
    SCI_RAG_GOOGLE_API_KEY=your-key-here
    ```

=== "Vertex AI"

    Same models, billed through a Google Cloud project you already have, no key to hand around. Authenticate once, then set the project:

    ```console
    $ gcloud auth application-default login
    ```

    ```dotenv title="~/.env"
    SCI_RAG_GCP_PROJECT=your-project-id
    ```

=== "Offline"

    No model at all. The kit uses a built-in embedder that matches on words rather than meaning:

    ```dotenv title="~/.env"
    SCI_RAG_EMBEDDING_PROVIDER=local-hash
    ```

    Parsing, chunking, storage, retrieval, and retrieval scoring all work. The graph, generated answers, and graded answers wait until you add a credential.

## 3. Install the project and create the database tables

```console title="Terminal"
$ make setup
```

`make setup` starts the selected database backend, installs dependencies, and creates the tables. Docker is the template default and listens on host port `5433`; projects generated with pixi or conda start a bundled server instead, and any project can point at a PostgreSQL 16 through 18 server you already run.

If port `5433` is already taken, usually by another Sci RAG Kit project whose database is running, change the `ports` entry in `docker-compose.yml` to `"5434:5432"` and set the same port in `SCI_RAG_DATABASE_URL`. [Troubleshooting](troubleshooting.md#docker) has the full recovery.

**Expected output**

```text
Database schema is up to date.
```

<div class="srag-checkpoint" markdown>
**Checkpoint: the foundation is healthy**

Run `uv run sci-rag doctor`. Configuration, domain, database, and schema should report healthy. An empty corpus, and a missing credential in Offline mode, are informational here.
</div>

## 4. Ingest the demo corpus

```console
$ make demo
```

This ingests five short synthetic documents about agricultural residues, runs one retrieval so you can see what comes back, and scores retrieval against the bundled test questions. The numbers in the documents are plausible but fictional; the corpus exists so the pipeline can be exercised before you commit your own documents.

**Expected output**

```text
Ingestion report
5 ingested, 0 skipped, 0 failed.

vector     success     ...
keyword    success     ...
graph      disabled    ...
```

`graph disabled` is normal here: the retrieval that `make demo` runs uses the fast profile, which leaves the model-dependent layers off.

<div class="srag-checkpoint" markdown>
**Checkpoint: you can see the evidence**

The retrieval table shows, for each result, a title, the section it came from, its license class, which layers found it, and an excerpt. The stage table says for each layer whether it succeeded, found nothing, was disabled, or failed. Nothing is silently omitted.
</div>

## 5. Ask a question

With a credential:

```console
$ uv run sci-rag answer "How much rice straw was generated in the Colusa Basin in 2023?"
```

The answer is approximately 302,000 dry tons and cites the synthetic resource assessment. Read the cited passage; the number alone is not the point.

In Offline mode this command retrieves normally, then declines to answer, naming the credential to set. It does not make an answer up.

If the stage table shows `timeout` for vector, graph, or HyDE, the model call was slow, not the corpus empty. Raise `SCI_RAG_PROVIDER_CALL_TIMEOUT_S` in `.env` (60 seconds by default) and try again.

## 6. Build the graph and take the deep path (optional)

With a credential:

```console
$ make demo-cloud
```

This extracts the demo domain's concepts and relationships from every chunk, summarizes the clusters they form, asks a question whose answer spans several documents, and scores retrieval with each layer switched off in turn. Reports land under `eval_results/`.

<div class="srag-checkpoint" markdown>
**Checkpoint: the graph produced evidence**

Open the newest report under `eval_results/`. It names the corpus, the models, the enabled layers, and a score per layer configuration. On five documents most rows score the same, which is expected; the spread appears as the corpus grows.
</div>

## 7. Serve it to people and agents

```console
$ uv run sci-rag serve
```

One process serves:

- an interactive API reference at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- a description of the corpus at [http://127.0.0.1:8000/v1/corpus-manifest](http://127.0.0.1:8000/v1/corpus-manifest)
- agent tools over MCP at `http://127.0.0.1:8000/mcp`

Try retrieval over REST:

```console
$ curl -s -X POST http://127.0.0.1:8000/v1/query \
    -H 'Content-Type: application/json' \
    -d '{"query": "rice straw availability", "top_k": 3}'
```

Connect a local agent such as Claude Code:

```console
$ claude mcp add demo-corpus -- uv run --directory "$(pwd)" sci-rag mcp
```

Ask the agent a question and tell it to use `demo-corpus`. You should see a `search_corpus` or `answer_question` tool call. An answer from the agent's own memory means the tool never fired.

<div class="srag-checkpoint" markdown>
**Checkpoint: one database, three front doors**

One Postgres database holds the documents, their chunks and vectors, the full-text index, and, if you ran step 6, the concept graph. One service answers the command line, REST clients, and agents the same way, and the reports under `eval_results/` record how it did on known questions.
</div>

## Next steps

- Replace the demo with your own documents. That is what the kit is for, and it is seven commands: [Bring your own domain](bring-your-own-domain.md)
- Something did not match this page: [Troubleshooting](troubleshooting.md)
- Understand what just happened, in plain words: [How it works](learn.md)
- Put the service somewhere other people can reach: [Deploy on Google Cloud](deploy-gcp.md)
