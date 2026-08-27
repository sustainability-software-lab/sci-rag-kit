# Choosing sci-rag-kit (or not)

An honest comparison against the systems you should also consider.
Short version: sci-rag-kit is an opinionated, evaluated TEMPLATE you
specialize into your field's knowledge base. If you want a library to
compose, a managed product, or an agentic literature assistant, better
options exist and are named below.

No benchmark-score comparisons appear here. Cross-system numbers on
hand-picked corpora mislead more than they inform; our own measured
numbers (on our own demo corpus, with confidence intervals and a
reproduction command) live in [benchmarks.md](benchmarks.md) and claim
nothing about anyone else.

## The landscape, honestly

**Microsoft GraphRAG** established the pattern this whole space builds
on (entity extraction, communities, global/local search) and its papers
remain the reference reading. As of mid-2026 the repository is in
maintenance mode: fine for study, a hard sell for a new deployment that
expects fixes and evolution.

**LightRAG** is the most active general-purpose GraphRAG library:
incremental insert/delete, dual-level retrieval, multiple storage
backends including Postgres, big community. It is a LIBRARY you build
an application around. If you want to write that application code and
make your own architecture calls, LightRAG is the strongest general
choice, and some of its ideas (per-document extraction caching) are on
our own roadmap, credited.

**PaperQA2** owns agentic scientific literature QA: multi-step
retrieve-summarize-answer loops over papers, with strong published
results on literature tasks. It is an agent with per-query LLM loops
(cost and latency to match), not an infrastructure template. For
"answer this hard question from the literature, take your time," pick
PaperQA2. Its evidence-summarization pattern is a Wave 2 candidate
here, credited.

**LlamaIndex (+ Neo4j)** gives maximal flexibility: every RAG pattern,
every store, endless composability. The flip side is that YOU are the
architect: chunking, graph store, eval, serving are all decisions you
make and own. Teams with strong LLM-engineering capacity build great
systems this way; teams whose job is the science, not the RAG, mostly
want those decisions made well and defensibly, once.

## What sci-rag-kit actually is

A GitHub template repository: you instantiate it, run
`scripts/init_domain.py`, edit three domain files (ontology, prompts,
seed questions), point it at your documents, and you have a running,
served, evaluated knowledge base whose every architectural decision is
written down with its reasoning (docs/methodology.md, docs/adr/).

The bets it makes for you, and where they hold:

| Axis | The kit's position | Choose differently if |
|------|--------------------|----------------------|
| Shape | Template repo you own and modify; ~60 files you can read in an afternoon | You want a pip-installable framework with a plugin ecosystem (LlamaIndex, LightRAG) |
| Storage | One Postgres database (pgvector + full-text + graph-as-rows); no second system to operate | Your graph needs >10M edges or dedicated graph algorithms (then a graph database earns its ops cost) |
| Evaluation | First-class: seed questions, layer ablations, bootstrap CIs, blind two-pass judge, kappa calibration, report diffing; the harness is citable in a methods section | You will never run an eval (be honest); any framework is fine and none will save you |
| License governance | Fail-closed license classes enforced inside every layer's SQL, before ranking; built for mixed-rights scientific corpora | Everything you index is uniformly licensed and served to one audience |
| Serving | REST + MCP from one FastAPI service; agents are first-class consumers | You need a hosted, managed product with an SLA (this is self-hosted infrastructure) |
| Retrieval philosophy | Fused layers + adaptive routing, no per-query agentic loop; latency and cost are predictable | You want deep multi-step agentic answering per query (PaperQA2) |

## The concessions, plainly

- **No agentic loop.** By design (predictable cost, honest evals), and
  the anti-recommendation is recorded in the methodology. If your
  questions genuinely need multi-step reasoning per query, use PaperQA2
  or add an agent ON TOP of the kit's API.
- **Postgres-only.** One database is the point. If that is a blocker,
  the kit is not for you; we will not grow a storage abstraction layer.
- **Google-first model wiring.** Gemini through AI Studio or Vertex is
  what ships and what gets tested. The `LLMClient`/`EmbeddingProvider`
  seams are small and other providers are a contribution away, but
  today that work is yours.
- **Early stage.** 0.x, small community, no history of external
  deployments yet. The eval harness and docs are ahead of the adoption
  curve on purpose; judge accordingly, and see
  [VERSIONING.md](VERSIONING.md) for exactly what 0.x promises.
- **English-centric defaults.** The keyword layer's full-text config
  and the demo prompts assume English scientific text.

## A decision rule that fits on an index card

- Building a knowledge base FOR a scientific field, want evaluation and
  license discipline built in, happy to own a small Postgres service:
  **use the template**.
- Building a bespoke application, want full architectural control:
  **LightRAG or LlamaIndex**.
- Want an assistant that answers hard literature questions with
  agentic effort per query: **PaperQA2**.
- Studying how GraphRAG works: **read Microsoft GraphRAG's papers**,
  then read our methodology doc for the disagreements.
