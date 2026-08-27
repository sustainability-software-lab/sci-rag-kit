# Quickstart

Setup through a served, agent-accessible RAG over the demo corpus, in
about ten minutes. Every command runs from the repository root.

## What you need

| Thing | Why | Get it |
|-------|-----|--------|
| Python 3.11+ and [uv](https://docs.astral.sh/uv/) | runs the kit | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Docker | one-command Postgres with pgvector | [docker.com](https://www.docker.com/) |
| A Google model credential (optional but recommended) | real embeddings, graph extraction, and answers | see step 2 |

No Docker? Any PostgreSQL 15+ with the pgvector extension works; point
`SCI_RAG_DATABASE_URL` at it and skip `docker compose`.

## Step 1: get the code

If you are starting your own project, click **Use this template** on
GitHub first, then clone your new repository. To just try the kit:

```bash
git clone https://github.com/sustainability-software-lab/sci-rag-kit.git
cd sci-rag-kit
```

## Step 2: configure credentials

```bash
cp .env.example .env
```

Open `.env` and pick ONE of three modes:

**Mode A, easiest: a free AI Studio key.** Get one at
[aistudio.google.com/apikey](https://aistudio.google.com/apikey) (free
tier is plenty for the demo), then set:

```
SCI_RAG_GOOGLE_API_KEY=your-key-here
```

**Mode B, for labs on Google Cloud: Vertex AI.** Authenticate once with
`gcloud auth application-default login`, then set:

```
SCI_RAG_GCP_PROJECT=your-project-id
```

**Mode C, no credentials at all.** Set
`SCI_RAG_EMBEDDING_PROVIDER=local-hash`. The pipeline runs fully offline
with a deterministic lexical embedder. Retrieval works mechanically
(good for seeing the plumbing), but rankings are word-overlap, not
meaning, and anything that needs an LLM (graph extraction, generated
answers) is unavailable. You can add a key later and re-ingest.

## Step 3: install and initialize

```bash
make setup
```

That runs three things you could also run yourself: `uv sync` (install),
`docker compose up -d --wait` (Postgres on port 5433, chosen to never
collide with a Postgres you already run), and `uv run sci-rag db upgrade`
(create the schema, including the vector and full-text indexes).

## Step 4: run the demo

```bash
make demo
```

This ingests the bundled demo corpus (five synthetic documents about
agricultural residues; realistic style, fictional numbers, CC0), runs a
retrieval you can inspect, and scores retrieval against the bundled seed
questions. You will see a stage table like:

```
│ vector    │ success │  ... │ 20 │
│ keyword   │ success │  ... │  4 │
│ graph     │ disabled │     │    │
```

`disabled` is normal at this point: the graph does not exist yet.

## Step 5: ask something

```bash
uv run sci-rag answer "How much rice straw was generated in the Colusa Basin in 2023?"
```

With a Google credential you get a short, cited answer (the correct demo
answer is about 302,000 dry tons, citing the resource assessment). In
offline mode this step reports that no LLM is configured, which is
itself the system working: it refuses rather than fakes.

## Step 6: build the graph and go deep

With a Google credential:

```bash
make demo-cloud
```

That extracts entities and relationships from every chunk (about a
minute on the demo corpus), clusters them into summarized communities,
asks a question that needs evidence from three documents at once, and
runs the full per-layer ablation report so you can see what each
retrieval layer contributes. Reports land in `eval_results/`.

## Step 7: serve it

```bash
uv run sci-rag serve
```

* Interactive API docs: http://127.0.0.1:8000/docs
* A retrieval call: `curl -s -X POST localhost:8000/v1/query -H 'Content-Type: application/json' -d '{"query": "rice straw availability"}'`
* The public corpus manifest: http://127.0.0.1:8000/v1/corpus-manifest
* MCP for agents, same process: http://127.0.0.1:8000/mcp

To wire a local agent over stdio instead:

```bash
claude mcp add demo-corpus -- uv run --directory $(pwd) sci-rag mcp
```

Then ask Claude Code something like "using the demo-corpus tools, what
biogas yield does pretreated rice straw achieve?" and watch it call
`search_corpus` and `answer_question`.

## Where to next

* Swap in your own field: [bring-your-own-domain.md](bring-your-own-domain.md)
* Understand what you just ran: [methodology.md](methodology.md)
* Put it on Google Cloud: [deploy-gcp.md](deploy-gcp.md)

## Troubleshooting

**`connection refused` on 5433.** Postgres is not up: `docker compose up
-d --wait`, or check `docker ps`. If you use your own Postgres, confirm
`SCI_RAG_DATABASE_URL` and that `CREATE EXTENSION vector` is available.

**`No Google credentials configured`.** The error tells you the three
options; it appears the moment something needs a model (answering,
extraction, HyDE), not at startup, so retrieval-only use works without
credentials.

**Embedding dimension errors.** The database columns are created with
`SCI_RAG_EMBEDDING_DIM` (default 1536) at migration time. If you change
the dimension or the embedding model family, re-create the schema (drop
and `sci-rag db upgrade`) and re-ingest; mixing dimensions is refused
loudly on purpose.

**PDF text looks mangled.** The pypdf fallback is doing its best with a
hard PDF. Install the good parser: `uv sync --extra docling` (large
download; it brings a table-structure model) and re-ingest.

**Ingest says `skipped_duplicate`.** Working as intended: identical
content is recognized by hash and never stored twice. Delete and
re-ingest only if you actually changed the file.
