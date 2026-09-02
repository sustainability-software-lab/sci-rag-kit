---
title: FAQ
description: Short answers to what Sci RAG Kit is, who it is for, and why each design decision went the way it did.
---

# Frequently asked questions

The reasoning behind the kit is written down at length in ten decision records and a methodology page. This page gives the answer first, the reason second, and a link to the long version.

## What this is

### What is Sci RAG Kit?

A project template for retrieval-augmented generation over scientific documents, on one Postgres database. You copy it, point it at your documents, and get a knowledge base that answers questions with numbered citations to the passages it used.

It parses PDF, HTML, Markdown, and text. It builds a knowledge graph from concepts you declare and searches with five retrieval layers that merge into one ranking. It includes an evaluation harness and one service that answers REST clients and agents. Everything is stored in Postgres with the pgvector extension.

### Who is it for?

A scientific group that needs a defensible knowledge base over its own literature and has no retrieval engineer to spare. The architectural decisions are made and written down with their reasons, so you can defend them in a review. The operational surface is one database, because a group without a platform team pays for every extra system.

If you are building a bespoke retrieval application and want to make every architectural call yourself, a library fits better. [Choosing Sci RAG Kit](choosing-sci-rag-kit.md) names the alternatives.

### Is this a library, a framework, or a template?

A template: a GitHub template repository that is itself a working application, with real code, a demo corpus, and green CI. You adapt it by editing data and configuration (the `domain/` folder, the corpus manifest, and `.env`). Nothing renames a Python package, and there are no placeholders to fill in. [Why a template repository and not a cookiecutter](#why-a-template-repository-and-not-a-cookiecutter) has the reasoning.

### What does "scientific" buy me over a general RAG framework?

Three things that break naive retrieval on scientific text. The evidence is numeric and tabular, so the chunker keeps each table intact. Questions and documents use different words, so retrieval combines keyword search and a hypothetical-answer search with the vector search. Corpora mix redistribution rights, so every document carries a license class that every layer enforces before ranking. [The methodology](methodology.md) traces each design choice back to one of the three.

### How does it compare to LightRAG, PaperQA2, or LlamaIndex?

They are different shapes. LightRAG and LlamaIndex are libraries you build an application around, and they win when you want to make the architectural calls yourself. PaperQA2 is an agent that reasons over papers in several steps per question, and it wins when a question is hard enough to be worth that cost and latency. This kit is infrastructure with the decisions already made and measured. [Choosing Sci RAG Kit](choosing-sci-rag-kit.md) is the comparison.

## Getting started

### What is the fastest way to try it?

Clone the repository and run the demo. In about ten minutes and with no credentials, it ingests five synthetic documents about agricultural residues, retrieves evidence for one question, and scores retrieval against the bundled test questions. To start a project of your own, run `pipx install sci-rag-kit` and then `sci-rag new`. The [quickstart](quickstart.md) has both routes.

### Do I need Google credentials?

Not to try it, and not to run retrieval. Yes for anything that calls a model. With `SCI_RAG_EMBEDDING_PROVIDER=local-hash` the kit uses an offline embedder that matches on words, and parsing, chunking, storage, retrieval, and retrieval scoring work. The graph, the hypothetical-answer search, community summaries, generated answers, and graded answers need a credential. Generation can use Gemini, Claude, or any OpenAI-compatible endpoint. Embeddings are Google-only, because changing the embedder means re-embedding every chunk in the database; see [why you can change the LLM but not the embedding provider](#why-can-i-change-the-llm-but-not-the-embedding-provider).

### Do I need Docker?

With pixi or conda, no: those managers install PostgreSQL and pgvector from conda-forge, keep the data in `.pgdata/`, and default to `SCI_RAG_DB_BACKEND=local`. With uv or venv + pip, Docker is the default and the easiest option, not a requirement. Every project can use `SCI_RAG_DB_BACKEND=local` when PostgreSQL 16 through 18 and pgvector are already installed, including Postgres.app, and every project can keep the optional Cloud SQL helper through Advanced setup. [ADR 0008](adr/0008-supported-postgresql-versions.md) records the supported range and [ADR 0009](adr/0009-cloud-dev-database.md) the Cloud helper.

### Do I have to clone the repository?

No. `pipx install sci-rag-kit` then `sci-rag new` fetches the template at a pinned tag and writes a configured, git-initialized project directory. Quick asks for six setup decisions and the credential value the selected mode needs. Advanced asks every applicable question. Choose Offline when you do not want a model credential.

Clicking **Use this template** or cloning works too. Run `sci-rag init` inside that checkout. It configures the same files without downloading a template or running the credential check. Both routes start from the same tree and use the same appliers.

### Can I run it completely offline?

Ingestion, retrieval, and retrieval scoring, yes. Answers, no. Set `SCI_RAG_EMBEDDING_PROVIDER=local-hash` and the demo and the whole test suite run without a network call. Asking for an answer in that state reports that no model is configured; it never invents one.

## Why it is built this way

Each answer gives the decision and its reason. The decision record behind it lists the alternatives, the consequences, and the conditions that would make us reverse it.

### Why is the knowledge graph in Postgres and not Neo4j?

Because this workload never issues the query a graph engine is for. The only traversal is a two-hop walk from a few seed entities to their evidence chunks, which is a recursive query over indexed foreign keys. A graph engine would add a second backup, migration, and access-control story for no query it needs. One database also lets a chunk and its graph rows commit together. Deep path queries and centrality are out of scope; export the two tables when you want them. [ADR 0001](adr/0001-graph-in-postgres.md).

### Why 1536-dimension embeddings when models offer 3072?

Because pgvector's HNSW index stops at 2000 dimensions. A 3072-dimension column falls back to exact scans, which read every row on every query. The default model supports truncation, so the first 1536 dimensions carry most of the signal at a small published cost, and every truncated vector is re-normalized. [ADR 0002](adr/0002-embeddings-1536-hnsw.md).

### Why is Docling an optional extra?

Because it installs several gigabytes of machine-learning dependencies. It is still the recommended PDF parser: run `uv sync --extra docling` and the parser uses it, because it recognizes table structure, which is where cheap parsers fail on scientific PDFs. Without it, pypdf is always available, at reduced table fidelity, and the parser records which route it took. [ADR 0003](adr/0003-docling-with-pypdf-fallback.md).

### Why a template repository and not a cookiecutter?

Because a cookiecutter template is code you cannot run. Its placeholders make the tree hard to browse, impossible to execute, and testable only by generating a project and looking. A runnable template inverts all three: you evaluate the kit by running it, the demo documents the behavior, and the CI that gates the application gates the template. The cost is less parameterization; disagreeing with an opinion is a normal code change in a repository you own. [ADR 0004](adr/0004-template-repo-not-cookiecutter.md).

### Why do citations get their own table?

Because a citation is not the kind of edge the knowledge graph stores. Graph edges run entity to entity, carry a type from your ontology, and quote the phrase that stated them. A citation runs document to document, has one type, and its evidence is a DOI match in a reference list. Forcing citations into the graph would put paper titles among concepts and have community detection summarize the mixture. So `document_citations` holds them. [ADR 0005](adr/0005-citation-edges-as-a-document-table.md).

### Why hand-written provider adapters?

Because the provider differences that matter are the ones a translation layer hides. Gemini's structured-output calls need thinking disabled or they return empty. Claude's nearest control is an effort setting with different semantics, and current Claude models reject the sampling parameters. Three adapters ship: `google`, `anthropic`, and `openai-compatible`, and the third covers Grok, Llama, Mistral, DeepSeek, OpenAI, and self-hosted servers. [ADR 0006](adr/0006-multi-provider-llms.md).

### Why can I change the LLM but not the embedding provider?

Because switching the embedder is a data migration. A migration fixes the vector dimension in the database column, and every chunk records the model that embedded it. Changing the embedder means a migration, a full re-embed, and an index rebuild, and a provider setting would present that as a one-line change. There is also little to switch to: Anthropic has no embedding API, and Vertex's managed text embeddings are Google's. You can point `SCI_RAG_EMBEDDING_MODEL` at another Google model, and `sci-rag embed reindex` plans the re-embedding. [ADR 0006](adr/0006-multi-provider-llms.md).

### Why does the generator configure files in place?

Because rendering placeholders would reintroduce everything the template decision avoids. `sci-rag new` downloads this repository at a pinned tag and rewrites its configuration files. Nothing in the tree is a placeholder, so the template stays browsable, runnable, and tested as itself. The wizard is ordinary tested code, and its outputs are loaded through the same models the application uses. [ADR 0007](adr/0007-interactive-project-generator.md).

### Will `--template-path` copy my credentials into a new project?

No. Generating from a local checkout copies the files git tracks and nothing else, so an ignored `.env`, proxy credentials, virtual environment, or Terraform state is never considered. A directory git knows nothing about falls back to a rule that lets nothing hidden through. [ADR 0010](adr/0010-template-copy-boundary.md).

### When should I use local PostgreSQL, Cloud SQL, or Docker?

Use Docker for the unchanged default with the fewest host prerequisites. Use local PostgreSQL for the fastest feedback loop without Docker. Use the Cloud SQL helper when several workspaces should share a managed instance without sharing database names or ports; its round trips make the integration suite slower. The cloud instance is development-only and reached through the IAM-authorized Cloud SQL Auth Proxy. [ADR 0009](adr/0009-cloud-dev-database.md).

### Why support three PostgreSQL majors?

Because nothing in the schema needs a particular major, and pixi and conda users often cannot install Docker. conda-forge builds pgvector against whatever server it currently ships, which is 18, while compose and CI run 16. The kit supports PostgreSQL 16 through 18 and tests both ends. [ADR 0008](adr/0008-supported-postgresql-versions.md).

## Retrieval and answers

### Why five retrieval layers? Is vector search not enough?

Because each layer finds evidence the others miss, and on scientific text the gaps are large. Vector search carries the highest weight. Keyword search catches exact terms, identifiers, and chemical names that embeddings blur. Graph traversal walks up to two hops from the concepts in the question, which brings in evidence whose words never appear in the question. Community summaries answer big-picture questions. The hypothetical-answer search bridges question wording and document wording. Not every layer runs every time: `interactive` uses vector and keyword only, and `deep` runs all five.

### Why merge by rank and not by score?

Because the layers' native scores are incomparable and their ranks are not. Each layer contributes `weight / (60 + rank)` per passage, so a passage several layers agree on beats one a single layer scored highly. The default weights are vector 1.5, keyword 1.0, graph 0.8, community 0.6, and hypothetical answer 1.2. They are defaults, not findings about your corpus; the [evaluation](evaluation.md) reports what each layer contributes before you change one.

### What is HyDE, and why is it never cited?

HyDE (hypothetical document embeddings) has a model write the short passage a real document would contain if it answered your question, then searches near that passage. It is never cited because it is not evidence. It is a guess used only to aim the search, and the domain profile can steer its style per question class.

### Why is the reranker off by default?

Because it has not earned the default on your corpus. Two adapters ship, one using the configured model and one using a local cross-encoder behind the `rerank` extra. Either stays off until the `with_rerank` against `no_rerank` comparison justifies the latency on the corpus you have. Answer compression is held to the same rule and passed it at a relevance floor of 0.0, so it ships on. [Benchmarks](benchmarks.md) publishes the runs.

### Why does the community layer skip my query when I filter?

Because a community summary was written from several documents before anyone's scope was known, and the prose cannot be separated afterward. When a request restricts license classes, sources, documents, or retractions, the layer reports `skipped` and the other four layers apply the scope inside their own queries.

### Why does it sometimes refuse to answer?

Because the alternative is an answer built from the model's memory. The answer prompt requires a numbered citation for every claim, prefers the sources' numbers and units, and says so when the sources do not contain the answer. Every real seed set keeps at least one `unanswerable` question so that behavior is measured.

## Rights and evidence

### Can I use this on papers I hold but may not redistribute?

Yes. Every document carries a license class from the manifest: `public`, `open_commercial`, `open_noncommercial`, `restricted`, or `unknown`. A paper you hold under a subscription is `restricted`. It can sit in the corpus and be retrieved by an internal caller whose scope allows that class, and it stays unreachable from a surface you do not control. Every layer applies the scope inside its own query, before ranking, so an ineligible document can never displace an eligible one. [Scope precedes ranking](methodology.md#7-scope-precedes-ranking) in the methodology has the full contract.

### Why does an empty license allowlist return nothing?

Because "allow nothing" and "no restriction" are different requests. `license_classes=None` means the caller did not restrict by license. `license_classes=()` means the caller allows nothing, and retrieval returns nothing before any embedding call or database query. Reading an empty list as "no restriction" would be an invisible failure.

### Why is `unknown` treated as unsafe?

Because "nobody has established the rights" is not "the rights are permissive". Missing or unrecognized license metadata normalizes to `unknown`, and `unknown` never enters a requested allowlist unless named. Only `public` and `open_commercial` are treated as safe for a service you do not fully control. Campaign discovery follows the same rule: a missing or unrecognized license signal stays `unknown`.

### Why does the grader never see the reference answer?

Because a grader that sees the expected answer rewards agreement with it, including agreement the cited sources do not support. Grading runs in two passes. The first sees the question, the answer, and the retrieved sources, and scores grounding, citation accuracy, and completeness. The second compares the answer to the reference without the sources and scores correctness. Both run at temperature 0, and a malformed grader response is recorded as a failure, never coerced into a score.

## Scale, cost, and operations

### How large a corpus can this handle?

The graph is sized for the hundreds to low tens of thousands of entities a domain corpus produces. Vector search stays indexed because the default dimension sits inside pgvector's limit, and graph traversal is a two-hop walk over indexed keys. The decision record's own revisit condition is a corpus reaching millions of entities or a product that needs three or more hops per query. At that point the graph layer is one stage behind the retrieval facade, so a graph engine replaces that one stage.

### What does it cost to run?

Locally, nothing beyond your machine and the model calls you make. Deployed, the database is the steady cost: the default `db-g1-small` Cloud SQL tier is a few tens of dollars a month, so destroy experiments with `terraform destroy`. Model cost follows the profile. `interactive` costs one query embedding; `deep` adds a generation call each for the graph and hypothetical-answer layers. There is no per-question agent loop, so cost per question is predictable.

### What happens when a retrieval layer times out?

It contributes no candidates, the request continues, and the trace says `timeout`. Each layer runs as its own task with its own database session and timeout. Traces carry stage, status, duration, and counts, never query or passage text, so they are safe to log.

## Extending and adapting

### Can I add my own parser, reranker, or model provider?

Yes. Those are three of the five boundaries the kit is built to vary at:

| Need | Contract | Primary file |
|---|---|---|
| New document type | produce the shared parsed block model | `src/sci_rag/ingest/parsers.py` |
| New source system | produce `CorpusEntry` values | `src/sci_rag/ingest/manifest.py` |
| New post-fusion ranking | implement `Reranker` | `src/sci_rag/retrieve/rerank.py` |
| New embedding or generation model | implement `EmbeddingProvider` or `LLMClient` | `src/sci_rag/embed/`, `src/sci_rag/llm/` |
| New identity system | implement `AuthBackend` | `src/sci_rag/server/auth.py` |

Anything that changes ranking owes a before-and-after evaluation. [Extend the kit](extend.md) is the walkthrough.

### Is there a plugin system?

No, on purpose. There is also no task queue, cache service, vector-store sidecar, or graph database. A small factory selects providers, so the supported set is visible in one file. Adding a fourth generation provider means writing an adapter next to the three that ship.

### Can I rename the Python package?

You can, but derived projects keep the `sci_rag` import path. Renaming buys nothing functional and costs the ability to diff your project against the upstream template and pull improvements. `sci-rag init` and `scripts/init_domain.py` set the project name and description without touching the import path.

### How much of this should I change?

As much as you need. The parts built to be replaced are `domain/`, the corpus manifest, and `.env`, and most projects never need more. Beyond them, the five boundaries above are where real projects vary. Keep two things if you can: run an evaluation before and after a retrieval change, and keep the rights scope inside every layer's query.

## The project

### Is this production ready? What does 0.x mean?

It is alpha, and 0.x promises something specific. Minor releases may break APIs, and the changelog says so under a "Breaking" heading with a migration note. Patch releases break nothing. Schema changes ship as migrations that run forward from any prior release. Evaluation report JSON only gains keys, and domain profiles written for an older 0.x keep working. The promise covers five surfaces: the documented Python exports, the CLI, the REST contract and MCP tools, the `domain/` format, and the report keys. [Versioning](VERSIONING.md) lists what 1.0 waits for.

### How do I cite it?

Cite the software title, the version or exact Git commit, the repository URL, and the access date. There is no archival DOI yet. A software citation alone does not identify a retrieval experiment, so also report the corpus snapshot and digest, the license scope, the model identifiers, the domain profile, the enabled layers, and the question set. [How to cite](citation.md) has the BibTeX.

### Who maintains it, and how are decisions made?

The Sustainability Software Lab at Berkeley Lab maintains it. Code-level decisions happen in pull requests and resolve by evidence. Architecture decisions get a decision record. Direction-level proposals start as a GitHub Discussion and become a record plus issues when they converge. [Governance](GOVERNANCE.md) has the roles.
