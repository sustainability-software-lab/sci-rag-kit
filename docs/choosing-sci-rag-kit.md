---
title: Choosing Sci RAG Kit
description: Compare Sci RAG Kit against LightRAG, PaperQA2, LlamaIndex, and Microsoft GraphRAG, then decide which one fits the work in front of you.
---

# Choosing Sci RAG Kit

Sci RAG Kit is an opinionated, evaluated template that configures into a field's knowledge base. For a library to compose, a managed product, or an agent that reasons over the literature per question, the systems below fit better. This page says which.

No cross-system benchmark scores appear here. Numbers measured on different corpora are not comparable. Our own numbers are on the [benchmarks page](benchmarks.md), measured on our demo corpus with confidence intervals and a reproduction command.

## The landscape

These readings were last checked as of 2026-08-28. Another project's status is the claim on this page most likely to go stale, so it carries a date.

**Microsoft GraphRAG** established the pattern this space builds on: entity extraction, communities, global/local search. Its papers remain the reference reading. The project is in maintenance mode per the README. Bug fixes and CVE updates continue, but not new features. The releases match: v3.1.2 in August 2026, with earlier releases consisting of dependency updates. It is good for study and for deployments where the current feature set already meets all requirements.

**LightRAG** is the most active general-purpose GraphRAG library. It offers incremental insert/delete, dual-level retrieval, multiple storage backends including Postgres, and a large community. It is a **library** to build an application around, not a ready-made application. For writing application code and making architectural calls, LightRAG is the strongest general choice. Some of its ideas, such as per-document extraction caching, are on our roadmap, credited.

**PaperQA2** owns agentic scientific literature QA: multi-step retrieve-summarize-answer loops over papers, with strong published results on literature tasks. It is an agent with per-query LLM loops (costs and latency to match), not an infrastructure template. For "answer this hard question from the literature, take your time," pick PaperQA2. Its evidence-summarization pattern shipped here in v0.3 as contextual snippet compression and cleared the paired judged-answer gate at a relevance floor of 0.0.

**LlamaIndex (+ Neo4j)** offers every RAG pattern and every store. The tradeoff is that the builder becomes the architect. Chunking, graph store, evaluation, and serving are decisions the team makes and owns. Teams with strong LLM-engineering capacity build good systems this way. Teams whose job is the science usually want those decisions made once, well, and defensibly.

## What sci-rag-kit is

A GitHub template repository. Run `pipx install sci-rag-kit` then `sci-rag new` writes a configured project; `sci-rag init` configures a checkout you already have. What you get is a running, served, evaluated knowledge base. The [quickstart](quickstart.md) is the walkthrough. The [FAQ](faq.md) covers who it is for and why each decision went the way it did. The [decision records](adr/0001-graph-in-postgres.md) hold the full arguments.

The bets it makes for you, and when to choose differently:

| Axis | The kit's position | Choose differently if |
|------|--------------------|----------------------|
| Shape | Template repo you own and modify; one Python package, no plugin layer between you and it | You want a pip-installable framework with a plugin ecosystem (LlamaIndex, LightRAG) |
| Storage | One Postgres database (pgvector + full-text + graph-as-rows); no second system to operate | Your graph needs >10M edges or dedicated graph algorithms (then a graph database earns its ops cost) |
| Corpus building | Discovery from a topic or DOI list, open-access rights resolved per paper, verified PDF download, abstract screening with a human review queue | You already have the documents and their rights, and want nothing between you and ingestion |
| Graph | Ontology-constrained extraction, reviewable entity resolution with an audit row per merge, and citation traversal over resolved DOI edges | You want an unconstrained graph and will do the disambiguation downstream |
| Evaluation | Built in: test questions, per-layer scores, confidence intervals, a two-pass grader, calibration against human labels, report diffing; the harness is citable in a methods section | You will not run an evaluation; then any framework is fine |
| License governance | License classes enforced inside every layer's query, before ranking; built for corpora with mixed rights | Everything you index is uniformly licensed and served to one audience |
| Model wiring | Gemini, Claude, and any OpenAI-compatible endpoint, chosen per role, so the model that answers need not be the model that grades | You want an embedding provider you can swap too; here that is a data migration (see the concessions) |
| Serving | REST + MCP from one FastAPI service; agents are first-class consumers | You need a hosted, managed product with an SLA (this is self-hosted infrastructure) |
| Retrieval philosophy | Five merged layers and a router, with no per-question agent loop, so latency and cost are predictable | You want multi-step agentic answering per question (PaperQA2) |

## The concessions

- **No agent loop.** Cost per question is predictable because the kit does one retrieval and one generation per question. For multi-step reasoning, use PaperQA2 or add an agent on top of the kit's API.
- **Postgres only.** One database is the point. The kit will not grow a storage abstraction layer.
- **Embeddings are Google-only.** Generation is not: the `google`, `anthropic`, and `openai-compatible` adapters cover Claude, Grok, Llama, Mistral, DeepSeek, OpenAI, and self-hosted vLLM or Ollama servers, selected per role. Changing the embedder requires a migration, a full re-embed, and an index rebuild (a data migration rather than a setting). See [ADR 0006](adr/0006-multi-provider-llms.md).
- **Features stay off until a measurement on the corpus turns them on.** Answer compression is on for the demo because its paired evaluation held at a relevance floor of 0.0 and failed at 0.15 and 0.3; [benchmarks.md](benchmarks.md) publishes those runs. Reranking is off until an evaluation justifies it.
- **Early stage.** 0.x, a small community, and no external deployments yet. [VERSIONING.md](VERSIONING.md) states exactly what 0.x promises.
- **English-centric defaults.** The keyword layer's full-text configuration and the demo prompts assume English scientific text.

## The decision rule

- Building a knowledge base for a scientific field with evaluation and license discipline built in, able to run a small Postgres service: use the template.
- Building a bespoke application with full architectural control: LightRAG or LlamaIndex.
- Building an assistant that answers hard literature questions with multi-step effort per question: PaperQA2.
- Studying how GraphRAG works: read Microsoft GraphRAG's papers, then the [methodology](methodology.md) for where this kit differs.
