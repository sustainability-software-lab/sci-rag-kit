# sci-rag-kit

**A do-it-yourself GraphRAG factory for scientific domains.** Point it at
a folder of papers, reports, and protocols, and get a grounded,
citation-backed question-answering system for your field: hybrid
retrieval over Postgres, a knowledge graph built from your own ontology,
an evaluation harness that keeps you honest, and serving over REST and
MCP so both humans and AI agents can use it.

This is a [GitHub template repository](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-repository-from-a-template).
Click **Use this template**, follow the ten-minute quickstart below, and
you have a working RAG over a demo corpus. Then swap in your own
documents and ontology, and it is yours.

## Why this exists

Every scientific group is sitting on a pile of domain documents and
wondering the same thing: can we ask it questions and trust the answers?
Getting from that pile to a trustworthy system involves a dozen
interlocking decisions (chunking, embeddings, graph extraction, fusion,
licensing, evaluation, serving) that are easy to get subtly wrong and
tedious to rebuild for every domain. This kit packages a
production-tested methodology into a template anyone can specialize:

- **Five fused retrieval layers.** Dense vectors, keyword full-text,
  knowledge-graph traversal, community summaries, and HyDE, combined by
  weighted reciprocal rank fusion. Multi-hop questions work because the
  graph connects evidence the words alone would miss.
- **Everything in one Postgres database.** Text, vectors (pgvector +
  HNSW), full-text indexes, and the graph, in plain rows. One backup, one
  migration story, no vector-store or graph-database sidecars.
- **Your domain is configuration, not code.** Entity types, relationship
  types, prompts, and evaluation questions live in one `domain/` folder.
  Specializing to a new field never means editing Python.
- **Licensing is fail-closed.** Every document carries a redistribution
  class; retrieval scopes are enforced inside every layer's SQL, before
  ranking; an empty allowlist returns nothing. Your paywalled PDFs cannot
  leak onto a public surface.
- **Answers cite or refuse.** Every claim carries a numbered citation you
  can check, and when the corpus lacks the answer, the system says so.
- **An evaluation harness that cannot flatter you.** Expert seed
  questions, per-layer ablations, and a two-pass LLM judge that grades
  grounding blind (it never sees the reference answer). Reports are
  stamped with a corpus fingerprint and git commit.
- **Agents are first-class.** A full MCP server (seven tools) ships
  alongside the REST API, backed by the same service, with API keys,
  scopes, rate limits, and a bring-your-own-LLM-key flow.

The methodology behind all of this is written up, decision by decision,
in [docs/methodology.md](docs/methodology.md).

## The ten-minute quickstart

You need: [uv](https://docs.astral.sh/uv/), Docker (for Postgres), and
optionally a free [Google AI Studio API key](https://aistudio.google.com/apikey)
for real embeddings and answers.

```bash
# 1. Get the code (or click "Use this template" first and clone yours)
git clone https://github.com/sustainability-software-lab/sci-rag-kit.git
cd sci-rag-kit

# 2. Configure. The defaults work; add your Google key for real models.
cp .env.example .env
#    In .env, set SCI_RAG_GOOGLE_API_KEY=...        (easiest)
#    or SCI_RAG_GCP_PROJECT=... for Vertex AI       (labs on Google Cloud)
#    or SCI_RAG_EMBEDDING_PROVIDER=local-hash       (no credentials at all)

# 3. Install, start Postgres, create the schema
make setup

# 4. Ingest the demo corpus and see retrieval work, with scores
make demo

# 5. Ask a real question (needs the Google key from step 2)
uv run sci-rag answer "What conversion route suits rice straw given its ash content?"
```

You should see an answer like this, built from three different demo
documents, every claim cited:

> Given its ash content, anaerobic digestion is a suitable conversion
> route for rice straw [2][4]. Rice straw has an ash content near 18
> percent, which includes high silica [2]. This high ash and silica limit
> direct combustion [2] and prevent its use in gasifiers due to
> accelerated clinker formation [5]. ... a mild alkali soak raises the
> biogas yield to 320 cubic meters per dry ton [1][3].

Then build the knowledge graph and try the full five-layer retrieval:

```bash
make demo-cloud    # graph extraction + communities + a deep answer + ablation report
uv run sci-rag serve   # REST API at /docs, MCP server at /mcp
```

The demo corpus is five synthetic documents about agricultural residues
(plausible numbers, entirely fictional, CC0). It exists so you can watch
every moving part work before you commit your own documents.

## Making it yours

The whole point. The five-step version:

1. Put your documents in `data/raw/` (PDF, Markdown, or plain text) and
   describe them in a corpus manifest (title, authors, license class).
2. Edit `domain/domain.yaml`: your domain's name, entity types,
   relationship types, and HyDE query classes.
3. Skim the five prompts in `domain/prompts/` and adjust the wording to
   your field.
4. Write ten `domain/eval_seed_questions.jsonl` questions a domain expert
   can vouch for.
5. Run `sci-rag ingest`, `sci-rag graph extract`, `sci-rag graph
   communities`, then `sci-rag eval retrieval --ablation` to see what you
   built.

The full walkthrough, with advice on each step, is
[docs/bring-your-own-domain.md](docs/bring-your-own-domain.md). Use
`uv run python scripts/init_domain.py` to rebrand the repo for your
project in one step.

## What is in the box

```
domain/            Your field: ontology, prompts, seed questions  <- you edit this
src/sci_rag/       The kit: ingest, embed, graph, retrieve, answer, evals, server, cli
data/demo/         The offline demo corpus (synthetic, CC0)
migrations/        Database schema (Alembic; pgvector + HNSW + FTS indexes)
tests/             73 tests, all runnable offline (deterministic local embedder)
infra/terraform/   Optional Google Cloud deployment (Cloud SQL + Cloud Run)
docs/              Methodology, tutorials, API reference, architecture decisions
```

The command line is the spine of everything:

| Command | What it does |
|---------|--------------|
| `sci-rag db upgrade` | Create or upgrade the database schema |
| `sci-rag ingest <folder>` (or `--manifest file.jsonl`) | Parse, chunk, embed, and store documents |
| `sci-rag graph extract` | Build the knowledge graph from ingested chunks |
| `sci-rag graph communities` | Cluster the graph and write summaries |
| `sci-rag retrieve "question"` | Inspect retrieval: ranked results plus per-layer traces |
| `sci-rag answer "question"` | A grounded, cited answer |
| `sci-rag eval retrieval [--ablation]` | Score retrieval against your seed questions |
| `sci-rag eval answers` | Generate and judge answers (blind grounding + correctness) |
| `sci-rag serve` | REST API (`/docs`) + MCP (`/mcp`) in one process |
| `sci-rag mcp` | MCP over stdio, for local agents like Claude Code |
| `sci-rag stats` | What is in the knowledge base |

Connect an agent in one line:

```bash
claude mcp add my-corpus -- uv run --directory /path/to/your/repo sci-rag mcp
```

## Documentation

| | |
|---|---|
| [Quickstart](docs/quickstart.md) | The ten minutes above, with troubleshooting |
| [Bring your own domain](docs/bring-your-own-domain.md) | The full specialization tutorial |
| [Methodology](docs/methodology.md) | Every design decision, with reasons |
| [Architecture](docs/architecture.md) | How the code is laid out and why |
| [Evaluation guide](docs/evaluation.md) | Seed questions, ablations, the blind judge |
| [API reference](docs/api.md) | REST endpoints, MCP tools, auth, error codes |
| [Deploying on Google Cloud](docs/deploy-gcp.md) | Cloud SQL + Cloud Run, with Terraform |
| [Decision records](docs/adr/) | The trade-offs, argued honestly |

## Requirements and defaults

Python 3.11+, PostgreSQL 15+ with pgvector (the bundled
`docker-compose.yml` provides it). Google models are the default
(`gemini-embedding-001` at 1536 dimensions, `gemini-2.5-flash` for
generation) through either a free AI Studio key or Vertex AI credentials;
a deterministic offline embedder covers tests and dry runs. PDF parsing
uses [Docling](https://github.com/docling-project/docling) when installed
(`uv sync --extra docling`; it is a large install) and falls back to
pypdf otherwise.

## Lineage and acknowledgments

sci-rag-kit generalizes the retrieval methodology developed for PISCES,
a bioprocess development platform built at Lawrence Berkeley National
Laboratory, and was created as part of a collaboration with the
University of Washington Scientific Software Engineering Center (UW SSEC)
under the Schmidt Sciences VIS program. The kit is a fresh,
domain-agnostic implementation of that methodology, built to be
specialized by any scientific group.

## License

BSD 3-Clause. See [LICENSE](LICENSE).
