---
title: Choosing Sci RAG Kit
description: Compare Sci RAG Kit against LightRAG, PaperQA2, LlamaIndex, and Microsoft GraphRAG, then decide which one fits the work in front of you.
---

# Choosing Sci RAG Kit

An honest comparison against the systems you should also consider.
Short version: sci-rag-kit is an opinionated, evaluated **template** you
configure into your field's knowledge base. If you want a library to
compose, a managed product, or an agentic literature assistant, better
options exist and are named below.

No benchmark-score comparisons appear here. Cross-system numbers on
hand-picked corpora mislead more than they inform. Our own measured
numbers live in [benchmarks.md](benchmarks.md), on our own demo corpus,
with confidence intervals and a reproduction command. They claim nothing
about anyone else.

## The landscape, honestly

These readings were last checked **as of 2026-08-28**. Another project's
status is the claim on this page most likely to go stale, so it carries a
date you can weigh rather than an undated assertion.

**Microsoft GraphRAG** established the pattern this whole space builds
on (entity extraction, communities, global/local search) and its papers
remain the reference reading. Its README says the project "is largely in
maintenance mode, and won't be accepting new PRs or implementing new
features", with bug fixes and dependency updates continuing, particularly
for CVEs. That is the maintainers' own description rather than ours, and
it matches what ships: v3.1.2 in August 2026, and releases before it that
are dependency sweeps and fixes. Fine for study, and a considered choice
rather than a default for a new deployment that expects the feature set
to grow.

**LightRAG** is the most active general-purpose GraphRAG library:
incremental insert/delete, dual-level retrieval, multiple storage
backends including Postgres, big community. It is a **library** you build
an application around. If you want to write that application code and
make your own architecture calls, LightRAG is the strongest general
choice. Some of its ideas, such as per-document extraction caching, are on
our own roadmap, credited.

**PaperQA2** owns agentic scientific literature QA: multi-step
retrieve-summarize-answer loops over papers, with strong published
results on literature tasks. It is an agent with per-query LLM loops
(cost and latency to match), not an infrastructure template. For
"answer this hard question from the literature, take your time," pick
PaperQA2. Its evidence-summarization pattern shipped here in v0.3 as
contextual snippet compression, credited, and it cleared the paired
judged-answer gate at a relevance floor of 0.0.

**LlamaIndex (+ Neo4j)** gives maximal flexibility: every RAG pattern,
every store, endless composability. The flip side is that **you** are the
architect: chunking, graph store, eval, serving are all decisions you
make and own. Teams with strong LLM-engineering capacity build great
systems this way; teams whose job is the science, not the RAG, mostly
want those decisions made well and defensibly, once.

## What sci-rag-kit actually is

A GitHub template repository. `pipx install sci-rag-kit` then `sci-rag-new`
runs a wizard that asks about your domain, credentials, ontology, corpus,
and environment manager, then writes a configured project. Inside a
checkout you already have, `sci-rag init` runs the same wizard, and
`scripts/init_domain.py` is the narrow path when all you want is to reset
the name and the seed questions. What you get is a running, served,
evaluated knowledge base.

That is the short version. This page is about how the kit compares to
other systems; for what it is, who it is for, and why each decision went
the way it did, the [FAQ](faq.md) answers all three, and the
[decision records](adr/0001-graph-in-postgres.md) hold the full arguments.

The bets it makes for you, and where they hold:

| Axis | The kit's position | Choose differently if |
|------|--------------------|----------------------|
| Shape | Template repo you own and modify; one Python package, no plugin layer between you and it | You want a pip-installable framework with a plugin ecosystem (LlamaIndex, LightRAG) |
| Storage | One Postgres database (pgvector + full-text + graph-as-rows); no second system to operate | Your graph needs >10M edges or dedicated graph algorithms (then a graph database earns its ops cost) |
| Corpus building | Campaign discovery from a topic or DOI list, fail-closed open-access resolution, verified PDF download, PRISMA-aligned screening with a human review queue | You already have the documents and the rights answer, and want nothing between you and ingestion |
| Graph | Ontology-constrained extraction, reviewable entity resolution with an audit row per merge, and citation traversal over resolved DOI edges | You want an unconstrained graph and will do the disambiguation downstream |
| Evaluation | First-class: seed questions, layer ablations, bootstrap CIs, blind two-pass judge, kappa calibration, report diffing; the harness is citable in a methods section | You will never run an eval (be honest); any framework is fine and none will save you |
| License governance | Fail-closed license classes enforced inside every layer's SQL, before ranking; built for mixed-rights scientific corpora | Everything you index is uniformly licensed and served to one audience |
| Model wiring | Gemini, Claude, and any OpenAI-compatible endpoint, chosen per role, so the model that answers need not be the model that grades | You want an embedding provider you can swap too; here that is a data migration (see the concessions) |
| Serving | REST + MCP from one FastAPI service; agents are first-class consumers | You need a hosted, managed product with an SLA (this is self-hosted infrastructure) |
| Retrieval philosophy | Fused layers + adaptive routing, no per-query agentic loop; latency and cost are predictable | You want deep multi-step agentic answering per query (PaperQA2) |

## The concessions, plainly

- **No agentic loop.** By design (predictable cost, honest evals), and
  the anti-recommendation is recorded in the methodology. If your
  questions genuinely need multi-step reasoning per query, use PaperQA2
  or add an agent **on top of** the kit's API.
- **Postgres-only.** One database is the point. If that is a blocker,
  the kit is not for you; we will not grow a storage abstraction layer.
- **Embeddings are Google-only.** Generation is not: `google`,
  `anthropic`, and `openai-compatible` adapters all ship, so Claude,
  Grok, Llama, Mistral, DeepSeek, OpenAI, and a self-hosted vLLM or
  Ollama server all work today, selected per role with a
  `provider:model` setting. Embeddings are the half that stays Google's,
  and deliberately: a migration bakes the dimension into the pgvector
  column, so changing embedder means a migration, a full re-embed, and
  an index rebuild. That is a data migration, and a provider flag would
  advertise it as a configuration change. See
  [ADR 0006](adr/0006-multi-provider-llms.md).
- **Nothing turns on until a paired run on your corpus says it
  should.** Compression and reranking both ship. Compression is on for
  the demo because its gate held there, at a relevance floor of 0.0; the
  same gate failed at 0.15 and 0.3, and [benchmarks.md](benchmarks.md)
  publishes those runs too. Reranking is still off, waiting for an
  ablation to earn it. If you want features that default on because they
  usually help, this project will keep disappointing you on purpose.
- **Early stage.** 0.x, small community, no history of external
  deployments yet. The eval harness and docs are ahead of the adoption
  curve on purpose; judge accordingly, and see
  [VERSIONING.md](VERSIONING.md) for exactly what 0.x promises.
- **English-centric defaults.** The keyword layer's full-text config
  and the demo prompts assume English scientific text.

## A decision rule that fits on an index card

- Building a knowledge base **for** a scientific field, want evaluation and
  license discipline built in, happy to own a small Postgres service:
  **use the template**.
- Building a bespoke application, want full architectural control:
  **LightRAG or LlamaIndex**.
- Want an assistant that answers hard literature questions with
  agentic effort per query: **PaperQA2**.
- Studying how GraphRAG works: **read Microsoft GraphRAG's papers**,
  then read our methodology doc for the disagreements.
