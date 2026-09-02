<p align="center">
  <img src="docs/assets/logo.png" alt="Sci RAG Kit" width="560">
</p>

<p align="center">
  <a href="https://github.com/sustainability-software-lab/sci-rag-kit/actions/workflows/ci.yml"><img src="https://github.com/sustainability-software-lab/sci-rag-kit/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://sustainability-software-lab.github.io/sci-rag-kit/"><img src="https://img.shields.io/badge/docs-GitHub%20Pages-005bfd.svg" alt="Documentation"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-BSD--3--Clause-blue.svg" alt="License: BSD-3-Clause"></a>
  <img src="https://img.shields.io/badge/python-3.11%20%7C%203.12-blue" alt="Python 3.11 | 3.12">
</p>

Retrieval-augmented generation, built around your scientific domain.

Put your papers and reports into one database, ask questions in plain
language, and get answers that cite the passages they came from. A template
repository for retrieval-augmented generation that is already assembled: you
supply the documents, name the concepts your field cares about, and write a
few questions with known answers so you can measure how well it works.

**Start a project** with two commands. `sci-rag new` asks a few questions
and writes a configured, git-initialized project:

```bash
pipx install sci-rag-kit
sci-rag new
```

**Try it first** by cloning this repository and running the demo corpus
(see [Set up](#set-up) below). The
[documentation site](https://sustainability-software-lab.github.io/sci-rag-kit/)
has the guided path; the [quickstart](docs/quickstart.md) takes about ten
minutes.

## Components

What you get, in the order a document meets it:

- **Ingestion.** PDF, HTML, Markdown, and plain-text files are split into
  passages that keep their section headings and whole tables. Duplicates are
  skipped. Each document records who wrote it and whether its text may be
  redistributed.
- **One database.** Passages, their vectors, a full-text index, and the
  concept graph all live in PostgreSQL with the pgvector extension. There is
  nothing else to run or back up.
- **A concept graph.** With a model credential, the kit reads every passage
  and pulls out the concepts and relationships your field cares about, using
  a short list of types you declare in `domain/domain.yaml`. Related concepts
  are clustered and summarized. This is what makes questions that span
  several documents work.
- **Five ways to search.** By meaning, by exact words, through the concept
  graph, through the cluster summaries, and by a model's guess at what an
  answering passage would say. The five result lists merge into one ranking,
  and the tool shows which one found each result.
- **Cited answers.** The model answers only from the passages retrieved,
  citing each by number. When the documents do not contain an answer, it
  says so.
- **Rights built in.** Every document carries a license class (`public`,
  `open_commercial`, `open_noncommercial`, `restricted`, or `unknown`). A
  request that restricts rights never sees passages outside its scope, so a
  shared endpoint cannot leak a paywalled PDF you hold internally.
- **Measurement.** Score retrieval and grade answers against questions with
  known answers, see what each search layer contributes on your corpus, and
  compare two runs. Every report records which documents and models produced
  its numbers.
- **Serving.** One process answers the command line, a REST API (with
  interactive docs at `/docs`), and agents over MCP, the protocol tools such
  as Claude Code use to call external systems. API keys with scopes and rate
  limits are built in.
- **Model choice.** Gemini by default, through a free Google AI Studio key or
  a Vertex AI project. Claude and any OpenAI-compatible endpoint are one
  setting away for generation. An offline mode runs everything except the
  graph and generated answers with no credential at all.

## Set up

Requirements: [uv](https://docs.astral.sh/uv/), Docker (or PostgreSQL 16
through 18 with pgvector; see below), and optionally a
[Google AI Studio API key](https://aistudio.google.com/apikey).

```bash
cp .env.example .env
chmod 600 .env          # owner only: it is about to hold a credential
```

In `.env`, set one of:

| Setting | When |
|---|---|
| `SCI_RAG_GOOGLE_API_KEY=...` | A free AI Studio key. Right for almost everyone. |
| `SCI_RAG_GCP_PROJECT=...` | Your lab already runs on Google Cloud (after `gcloud auth application-default login`). |
| `SCI_RAG_EMBEDDING_PROVIDER=local-hash` | No credential yet. Retrieval works; the graph and generated answers wait. |

Then:

```bash
make setup     # install dependencies, start Postgres, create the tables
make demo      # ingest the demo corpus, run a retrieval, score it
```

`make setup` starts the selected database backend and creates every table.
Docker is the template default; a project can also use a conda-forge
server, a system PostgreSQL such as Postgres.app, or a Cloud SQL development
instance. [Run Postgres your way](docs/run-postgres.md) covers each.

With a credential configured, the graph and the answers work too:

```bash
uv run sci-rag answer "What conversion route suits rice straw given its ash content?"
make demo-cloud        # build the graph, ask a multi-document question, score each layer
uv run sci-rag serve   # REST at /docs, MCP at /mcp
```

The demo corpus is five short synthetic documents about agricultural
residues, with plausible but fictional numbers, so the pipeline can run end
to end before you commit your own documents.

## Use your own documents

Seven commands, each explained in
[Bring your own domain](docs/bring-your-own-domain.md):

```bash
uv run sci-rag draft manifest --folder data/raw      # 1. describe the documents you put in data/raw/
uv run sci-rag manifest lint data/corpus.jsonl        # 2. check the description (and decide rights)
uv run sci-rag draft ontology --folder data/raw       # 3. name the concepts your field cares about
uv run sci-rag build --manifest data/corpus.jsonl     # 4. ingest, then build the graph
uv run sci-rag draft questions --count 10             # 5. draft questions with known answers
uv run sci-rag eval retrieval --ablation              # 6. measure
uv run sci-rag answer "a question in your field"      # 7. ask
```

The three `draft` commands write a file for you to review, and each also
works with no model credential: `--print-prompt` gives you the prompt to
paste into any assistant, and `--from-file` reads the reply back. Two things
are never drafted for you: a document's rights, and the labels used to
check the answer grader against human judgment.

In a hurry? `uv run sci-rag build data/raw` ingests a folder with no
manifest at all and builds the graph when a credential is present.

## Commands

The ones you will use most. `uv run sci-rag --help` groups all of them by
stage, and the [CLI reference](docs/cli.md) lists every option.

| Command | What it does |
|---------|--------------|
| `sci-rag new` | Create a configured project |
| `sci-rag doctor` | Check configuration, database, corpus, and credentials in one pass |
| `sci-rag build <folder>` or `--manifest file.jsonl` | Ingest documents, then build the graph |
| `sci-rag draft manifest`, `draft ontology`, `draft questions` | Draft the domain files from your own documents |
| `sci-rag retrieve "question"` | Show the evidence, layer by layer |
| `sci-rag answer "question"` | A cited answer |
| `sci-rag eval retrieval --ablation` | Score retrieval and each layer's contribution |
| `sci-rag eval answers` | Generate and grade answers |
| `sci-rag campaign discover --topic ...` | Find papers to add, with their rights |
| `sci-rag serve` | REST and MCP server |
| `sci-rag stats` | What is in the knowledge base |

Register the MCP server with a local agent:

```bash
claude mcp add my-corpus -- uv run --directory /path/to/your/repo sci-rag mcp
```

## Repository layout

```
domain/            Your field: concepts, prompts, test questions
data/raw/          Your documents; data/corpus.jsonl describes them
data/demo/         The demo corpus (synthetic, CC0)
src/sci_rag/       The pipeline: ingest, embed, graph, retrieve, answer, evals, server, cli
migrations/        Database tables
tests/             Runs offline; database tests use a disposable database
infra/terraform/   Optional Google Cloud deployment
docs/              This documentation
```

## Documentation

The complete site is at
[sustainability-software-lab.github.io/sci-rag-kit](https://sustainability-software-lab.github.io/sci-rag-kit/).

| | |
|---|---|
| [Quickstart](docs/quickstart.md) | Install, run the demo, serve it. Ten minutes. |
| [Bring your own domain](docs/bring-your-own-domain.md) | The seven-command recipe, step by step |
| [How it works](docs/learn.md) | What happens between a document and a cited answer, in plain words |
| [FAQ](docs/faq.md) | Short answers, and the reasoning behind each design decision |
| [Troubleshooting](docs/troubleshooting.md) | From the symptom to the fix |
| [Evaluate your pipeline](docs/evaluation.md) | Seed questions, per-layer scores, the answer grader |
| [Run a corpus campaign](docs/campaigns.md) | Find papers by topic or DOI list, with their rights |
| [Run Postgres your way](docs/run-postgres.md) | Docker, conda-forge, a system server, or Cloud SQL |
| [Deploy on Google Cloud](docs/deploy-gcp.md) | Cloud SQL and Cloud Run from the included Terraform |
| [REST, MCP, and Python API](docs/api.md) | Endpoints, agent tools, keys, errors |
| [Architecture](docs/architecture.md) and [Methodology](docs/methodology.md) | How the code is shaped, and why |
| [Choosing Sci RAG Kit](docs/choosing-sci-rag-kit.md) | An honest comparison with GraphRAG, LightRAG, PaperQA2, LlamaIndex |
| [Benchmarks](docs/benchmarks.md) | Measured demo-corpus results, reproducible with `make benchmark` |
| [Decision records](docs/adr/) | The architectural bets, with the conditions that would reverse them |

## Requirements and defaults

Python 3.11 or 3.12. PostgreSQL 16 through 18 with pgvector; Docker is the
template default and matches CI. Embeddings come from Google's
`gemini-embedding-001` at 1536 dimensions, and generation defaults to a
Gemini model (`uv run sci-rag doctor` prints the current one). Docling gives
the best PDF parsing and is an optional extra (`uv sync --extra docling`)
because of its size; without it, pypdf handles PDFs with reduced table
fidelity.

## License

BSD 3-Clause. See [LICENSE](LICENSE).
