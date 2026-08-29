---
title: FAQ
description: Short answers to what Sci RAG Kit is, who it is for, and why each design decision went the way it did.
---

# Frequently asked questions

The reasoning behind this kit is written down at length, in ten decision records and a methodology specification. This page is the short version: the answer first, the reason after it, and a link to the long argument when you want it.

## What this is

### What is Sci RAG Kit?

A template repository for retrieval-augmented generation over a collection of scientific documents, running on one Postgres database. You copy it, point it at your literature, and get a knowledge base that answers questions with numbered citations back to the passages it used.

Concretely, that means structure-aware ingestion for PDF, Markdown, and text, and a knowledge graph built from an ontology you declare. Five retrieval layers run in parallel and fuse into one ranking. Answers are generated from that evidence, an evaluation harness measures them, and one service exposes the whole thing over REST and MCP. Everything is stored in Postgres with the pgvector extension. There is no second database.

### Who is it for?

A small scientific group that needs a defensible knowledge base over its own literature, and has no retrieval engineer to spare.

That shapes two things. The architectural decisions are made for you and written down with their reasoning, so you can defend them in a review without re-deriving them. And the operational surface is one database, because a group with no platform team pays the cost of a second one every week.

If you are building a bespoke retrieval application and want to own every architectural call, a library is a better fit than a template. [Choosing Sci RAG Kit](choosing-sci-rag-kit.md) names the alternatives.

### Is this a library, a framework, or a template?

A template, and specifically a GitHub template repository that is itself a working application: real code, a real demo corpus, green CI, and a "Use this template" button.

That matters for how you adapt it. You edit data and configuration: the `domain/` folder, the corpus manifest, and `.env`. Nothing renames a Python package, and there are no placeholders to fill in. The thing you read is the thing you run, before and after. [Why a template repository and not a cookiecutter](#why-a-template-repository-and-not-a-cookiecutter) has the reasoning.

### What does "scientific" buy me over a general RAG framework?

Three things a general framework leaves to you, because scientific question answering breaks naive retrieval in three specific ways.

The evidence is numeric and tabular, so the chunker keeps each table intact as its own chunk; a fixed-window splitter would shred it across three. Questions and documents use different words, so retrieval fuses keyword search and a hypothetical-document probe alongside the vector layer. And corpora mix redistribution rights, so a license class is a fail-closed property that every layer applies inside its own SQL, before ordering and limiting.

[The methodology](methodology.md) traces every other choice back to one of those three.

### How does it compare to LightRAG, PaperQA2, or LlamaIndex?

They are different shapes, and the comparison is about fit. LightRAG and LlamaIndex are libraries you build an application around, and they win when you want to make the architectural calls yourself. PaperQA2 is an agent that spends multi-step reasoning per query, and it wins when the question is hard enough to be worth that cost and latency.

This kit is infrastructure with the decisions already made and measured. [Choosing Sci RAG Kit](choosing-sci-rag-kit.md) is the honest comparison, on axes other than benchmark scores.

## Getting started

### What is the fastest way to try it?

Clone the repository and run the demo. Ten minutes, no credentials: it ingests five synthetic CC0 documents about agricultural residues, retrieves evidence for one question, and scores that retrieval against the bundled seed questions.

To start a project of your own instead, `pipx install sci-rag-kit` then
`sci-rag new` runs the wizard. The [quickstart](quickstart.md) has the commands
for both.

### Do I need Google credentials?

Not to try it. Not to run retrieval. Yes for anything that calls a model.

With `SCI_RAG_EMBEDDING_PROVIDER=local-hash` the kit uses a deterministic offline embedder, and parsing, chunking, storage, ranking, and retrieval evaluation all work. Similarity is lexical, which is a real quality drop, and the docs say so everywhere it matters.

Graph extraction, HyDE, community summaries, generated answers, and model-based judging need a credential. Generation can be Gemini, Claude, or any OpenAI-compatible endpoint. Embeddings are Google-only, for the reasons under [why you can change the LLM but not the embedding provider](#why-can-i-change-the-llm-but-not-the-embedding-provider).

### Do I need Docker?

It depends on your environment manager, and the answer changed recently.

With pixi or conda, no. Those managers bundle `postgresql` and `pgvector`
from conda-forge and keep their data in `.pgdata/`.

With uv or venv + pip, Docker is the easiest default, not a requirement. Every
manager can use `SCI_RAG_DB_BACKEND=local` when PostgreSQL 16 through 18 and
pgvector are already on the machine, including Postgres.app. Every manager can
also retain the optional Cloud SQL helper through Advanced setup.

[ADR 0008](adr/0008-supported-postgresql-versions.md) records the supported
server range. [ADR 0009](adr/0009-cloud-dev-database.md) records the system-local
and Cloud helper expansion.

### Do I have to clone the repository?

No. `pipx install sci-rag-kit` then `sci-rag new` fetches the template at a
pinned tag and writes a configured, git-initialized project directory. Quick
asks for six setup decisions and the credential value required by the selected
mode; Advanced exposes every applicable option. Choose Offline explicitly when
you do not want a model credential.

Clicking **Use this template** or cloning works too. Run `sci-rag init` inside
that checkout; it configures the same files without downloading a template or
running the new-project credential check. Both routes start from the same live
tree and use the same appliers.

### Can I run it completely offline?

Ingestion, retrieval, and retrieval evaluation, yes. Answers, no.

Set `SCI_RAG_EMBEDDING_PROVIDER=local-hash` and the whole test suite and the demo run without a network call. What you lose is everything that needs a model: the knowledge graph, community summaries, HyDE, generated answers, and the judge. Asking for an answer in that state reports that no LLM is configured. That is the same refusal the kit gives when retrieval finds nothing.

## Why it is built this way

Each answer here gives the decision and the reason it went that way. The [decision record](adr/0001-graph-in-postgres.md) behind it carries the alternatives we weighed, the consequences we accepted, and the conditions that would make us reverse it. Reach for the record when you are about to change the decision.

### Why is the knowledge graph in Postgres and not Neo4j?

Because this workload never issues the query a graph engine is for, and a second database costs more than it saves.

The only traversal here is a two-hop walk from a handful of seed entities back to their evidence chunks. That is a recursive query over indexed foreign keys, comfortably fast at the scale a domain corpus reaches. A graph engine would buy you that and charge a second backup story, a second migration story, a second access-control model, and a consistency seam between the graph and the chunks it points at. One database also lets a chunk and its graph rows commit together. The cost is deep path queries and centrality, which are out of scope; export the two tables when you want them.

Full argument and reversal conditions: [ADR 0001](adr/0001-graph-in-postgres.md).

### Why 1536-dimension embeddings when models offer 3072?

Because pgvector's HNSW index tops out at 2000 dimensions. A 3072-dimension column silently falls back to exact scans, where every vector query reads every row.

At ten thousand chunks you would not notice. Past that it hurts, and it is the kind of slowdown that arrives only once the corpus is too big to re-embed casually. The default model is trained with Matryoshka representation learning, so the first 1536 dimensions carry most of the signal at a small, published cost in quality. Truncation breaks the unit norm that cosine ranking assumes, so every vector is re-normalized, and the dimension is asserted twice: once by the provider, once by the database column. Full 3072 dimensions would retrieve slightly better. Measure that gap before paying the exact-scan price.

Full argument and reversal conditions: [ADR 0002](adr/0002-embeddings-1536-hnsw.md).

### Why is Docling an optional extra?

Because it pulls several gigabytes of machine-learning stack, and a hard dependency that size would tax everyone who never opens a PDF.

Docling is still the route we recommend. Run `uv sync --extra docling` and the parser picks it up automatically, because it does real layout analysis and table-structure recognition, and tables are where cheap parsers fail on scientific PDFs. Without it, pypdf is always there. Both routes and native Markdown converge on one block model, so nothing downstream knows which one ran. A corpus ingested with pypdf does have worse table fidelity, which is why the parser records the route it took.

Full argument and reversal conditions: [ADR 0003](adr/0003-docling-with-pypdf-fallback.md).

### Why a template repository and not a cookiecutter?

Because a cookiecutter template is dead code, and this one has to be inspectable to be trusted.

Cookiecutter parameterizes everything, and the price is a tree of placeholders you cannot browse comfortably, cannot run, and cannot test as itself. You find template bugs by generating a project and looking. A runnable template inverts all three: a newcomer evaluates the kit by reading and running it before committing, the demo documents the behavior, and the CI that gates any application gates template quality. What you give up is deep parameterization, license choice and layout variants among it. This template has opinions, and disagreeing with one costs you a normal code change in a repository you own.

Full argument and reversal conditions: [ADR 0004](adr/0004-template-repo-not-cookiecutter.md).

### Why do citations get their own table?

Because a citation is not the kind of edge the knowledge graph stores, and forcing it in would corrupt the graph.

`kg_relationships` is entity-to-entity by contract: both endpoints are foreign keys into `kg_entities`, the type has to be one the ontology declares, and every row carries the chunk and the quoted phrase that stated it. A citation has none of those. It runs document to document, its type never varies, and its evidence is a DOI match in a reference list. The workaround that would preserve the table, one synthetic entity per document, makes entity search return paper titles alongside concepts and has community detection summarize the mixture. So `document_citations` holds them, and only where both documents are in the corpus.

Full argument and reversal conditions: [ADR 0005](adr/0005-citation-edges-as-a-document-table.md).

### Why hand-written provider adapters?

Because the provider differences that matter here are the exact ones a translation layer smooths over.

JSON-mode calls set `thinking_budget=0` on Gemini for a documented reason: without it, extraction and judging spend the whole output budget thinking and return empty. Claude's nearest knob is `output_config={"effort": "low"}`, which has different semantics, because disabling thinking on current Claude models can leak reasoning tags into the JSON those call sites parse. Those models also dropped the sampling parameters, so the adapter omits `temperature` entirely. Three adapters ship: `google`, `anthropic`, and `openai-compatible`. The third covers Grok, Llama, Mistral, DeepSeek, OpenAI, and a self-hosted vLLM or Ollama server, since Vertex serves its partner models behind an OpenAI-compatible endpoint.

Full argument and reversal conditions: [ADR 0006](adr/0006-multi-provider-llms.md).

### Why can I change the LLM but not the embedding provider?

Because switching embedder is a data migration wearing a configuration flag's clothes.

A migration bakes `SCI_RAG_EMBEDDING_DIM` into the pgvector column, and every chunk records the version that produced it. Changing the embedder means a migration, a full re-embed, and an index rebuild. A provider setting would advertise all of that as a one-line config change. There is also little to switch to: Anthropic ships no embedding API, and Vertex's only managed text embeddings are Google's, so the alternatives mean deploying and paying for a GPU endpoint. You can point `SCI_RAG_EMBEDDING_MODEL` at a different Google model freely, and `sci-rag embed plan` scopes the re-embedding work when you need more.

Full argument and reversal conditions: [ADR 0006](adr/0006-multi-provider-llms.md).

### Why does the generator configure files in place?

Because a generator that rendered placeholders would drag back everything the template decision refused.

`sci-rag new` downloads this repository at a pinned tag and rewrites its
configuration files in place. There is no `{{ }}` syntax and no `{{ }}` directory
anywhere in the tree, and a test asserts a generated project contains no bare `{{`
in any Markdown, TOML, YAML, or JSONL file. The generator fetches this repository
byte for byte, so the template stays browsable, runnable, and tested as itself. The
wizard is ordinary tested code under `src/sci_rag/scaffold/`, and the appliers
round-trip their output through the same models the application loads, so a
generated profile cannot be something `load_domain()` would reject.

Full argument and reversal conditions: [ADR 0007](adr/0007-interactive-project-generator.md).

### Will `--template-path` copy my credentials into a new project?

No. Generating from a local checkout copies the files that checkout tracks, and
nothing else.

That matters because a checkout is not a template. Yours also holds a filled in
`.env`, cached proxy credentials, a virtualenv, Terraform state that contains a
generated database password, and whatever corpus you last ingested. Asking git
which paths are tracked draws the boundary from the repository itself, so an
ignored file is never even considered for copying, and the offline route ends up
with the same content the download route produces. A directory git knows nothing
about, such as an extracted archive, falls back to a fail closed rule: nothing
hidden crosses unless the template genuinely ships it.

Full argument and reversal conditions: [ADR 0010](adr/0010-template-copy-boundary.md).

### When should I use local PostgreSQL, Cloud SQL, or Docker?

Use local PostgreSQL for the fastest Docker-free feedback loop, Cloud SQL when
separate workspaces should share a managed instance without sharing database
names or ports, and Docker when you want the unchanged default with the fewest
host prerequisites. Postgres.app and the conda-forge server both drive the
same project-local helper. The cloud backend assigns each workspace its own
development database, destructive-test database, proxy process, and loopback
port, but its WAN round trips make the integration suite materially slower.

The cloud instance is development-only. Its public endpoint has no authorized
networks, and developers reach it through the IAM-authorized, TLS-encrypted
Cloud SQL Auth Proxy. [ADR 0009](adr/0009-cloud-dev-database.md) records the
security revision, scoped IAM permissions, measured latency, and cost-control
tradeoffs.

### Why support three PostgreSQL majors?

Because nothing in the schema needs a particular major, and pinning one would have cost an audience the project had just invited.

pixi and conda landed because scientific and national-lab users asked for them, and those users often cannot install Docker on a managed laptop or a cluster login node. conda-forge ships PostgreSQL and pgvector together, but it builds the extension against whatever server it currently carries, which is 18 today, while compose and CI run 16. The project could have moved everyone to 18, pinned those users to a two-year-old extension, or let the two diverge untested. It supports PostgreSQL 16 through 18 and tests both ends. Nothing in the schema objects: one HNSW index, no pgvector feature newer than 0.5, no version-specific SQL.

Full argument and reversal conditions: [ADR 0008](adr/0008-supported-postgresql-versions.md).

## Retrieval and answers

### Why five retrieval layers? Is vector search not enough?

Because each layer finds evidence the others miss, and on scientific text those gaps are large.

Dense vector search over chunk embeddings is the workhorse and carries the highest fusion weight. Keyword full-text search catches exact terms, identifiers, and chemical names that embeddings blur. Knowledge-graph traversal walks up to two hops from the entities in your question, so the connecting entity brings its evidence along even when the question's words never appear in that text. Community summaries answer big-picture questions no single chunk covers. HyDE writes the passage a real document would contain if it answered the question, then searches near that, which bridges the gap between how questions and documents are phrased.

Not all five run every time. Two profiles set the defaults: `interactive` uses vector and keyword only, with short timeouts, for humans waiting on a spinner, and `deep` runs all five for agents, batch jobs, and evaluation.

### Why fuse by rank and not by score?

Because the native scores are incomparable across layers and the ranks are not.

Cosine distance, `ts_rank`, and hop counts have different ranges and different meanings, so no amount of scaling makes them a shared currency. Weighted reciprocal rank fusion sidesteps the problem: each layer contributes `weight / (k + rank)` with rank starting at 1 and `k = 60`, so a candidate that several layers agree on beats a candidate one layer loved.

| Layer | Default weight |
|-------|---------------:|
| vector | 1.5 |
| keyword | 1.0 |
| graph | 0.8 |
| community | 0.6 |
| HyDE | 1.2 |

Those weights are defaults, not findings about your corpus. The evaluation harness's [ablation mode](evaluation.md) reports what each layer actually contributes to hit rate before you touch one.

### What is HyDE, and why is it never cited?

HyDE stands for hypothetical document embeddings. A fast model writes the short passage a real document would contain if it answered your question, that passage embeds as a document, and vector search runs near it.

It is never cited because it is not evidence. Nothing in it was retrieved from your corpus; it is a model's guess about what an answer might look like, used only to aim the search. Showing it or citing it would put unsourced model output in front of a reader wearing the same numbered-citation formatting as a real passage. So the generated passage is a search probe, never displayed and never cited, and the domain profile can steer its style per query class.

### Why is the reranker off by default?

Because it has not earned the default on your corpus, and the project will not turn something on from intuition.

A `Reranker` protocol ships with two adapters: an LLM one that needs no new dependencies, and a local cross-encoder behind the `rerank` extra. Both stay off until the `with_rerank` against `no_rerank` ablation justifies the latency on the corpus you actually have.

Contextual compression is held to the same rule, and it passed. The v0.3 gate swept the relevance floor: at 0.15 and 0.3 the floor discarded evidence the answer then could not ground itself in, and groundedness fell. At 0.0, where every source is summarized and none dropped, three paired runs held every judged dimension while median prompt tokens fell about a quarter. So compression ships on, at floor 0.0, and reranking is still waiting. [Benchmarks](benchmarks.md) publishes all of it, including the two floors that failed.

### Why does the community layer skip my query when I filter?

Because a community summary was written before anyone's scope was known, and it cannot be unmixed afterwards.

The layer clusters tightly connected entities, has a model write a short summary of each cluster, and embeds those summaries. A summary therefore aggregates evidence from several documents into one piece of prose. Say your request restricts license classes, sources, excluded documents, or known retractions. There is no reliable way to separate the allowed contributions from the disallowed ones inside that prose. So the stage disables itself, because the alternative is returning a summary partly built from documents you are not entitled to see.

That is a visible recall tradeoff, reported as `skipped` in the trace, not a silent one. Vector, keyword, graph, and HyDE still run and still apply your scope inside their own SQL.

### Why does it sometimes refuse to answer?

Because the alternative is a confident answer built from model priors, which is the failure this kit exists to avoid.

The answer prompt carries three standing orders: cite every claim inline by number, prefer the sources' numbers and units over summary, and say so when the sources do not contain the answer. A refusal means retrieval found nothing in scope, and it is more useful than a plausible paragraph you would have to go and check. The evaluation harness keeps at least one question tagged `unanswerable` in every real seed set for exactly this reason, so the honesty behavior is measured.

## Rights and evidence

### Can I use this on papers I hold but may not redistribute?

Yes. That case is exactly why rights are a first-class property here.

Every document carries a redistribution class declared in the corpus manifest: `public`, `open_commercial`, `open_noncommercial`, `restricted`, or `unknown`. A paper you hold under a subscription is `restricted`. It can sit in the corpus and be retrieved by an internal caller whose scope allows that class, while staying unreachable from a surface you do not fully control. A retrieval scope is the caller's rights, not a display preference.

The distinction that makes this work is where the filter runs. Every layer applies its license, source, year, author, journal, document, and DOI conditions inside its own SQL, before ordering and limiting. Filtering afterwards would be wrong twice: an ineligible row could crowd an eligible one out of a bounded candidate pool, then vanish, leaving excluded content shaping what survived.

[Evidence and rights](evidence-and-rights.md) has the full contract.

### Why does an empty license allowlist return nothing?

Because "I allow nothing" and "I did not restrict by license" are different requests, and conflating them fails open.

`license_classes=None` means the caller did not restrict by license. `license_classes=()` means the caller explicitly allows nothing, and retrieval returns nothing, before any embedding call or database query. Reading an empty allowlist as "no restriction" is the classic fail-open bug, and it would be invisible: the caller would get results and have no reason to suspect the filter never applied.

### Why is `unknown` treated as unsafe?

Because "nobody has established the rights" is not the same as "the rights are permissive", and only one of those is safe to get wrong.

Missing or unrecognized license metadata normalizes to `unknown`, which never silently enters a requested safe allowlist. Only `public` and `open_commercial` are treated as safe for surfaces you do not fully control. A caller who genuinely wants unestablished-rights material has to ask for `unknown` by name, which turns an accident into a decision.

The same reasoning runs through the corpus campaign path. Discovery produces candidate metadata only, and a missing or unrecognized license signal stays `unknown`. Nothing infers it from a title or a failed request.

### Why does the judge never see the reference answer?

Because a judge that sees the expected answer rewards agreement with it, including agreement the retrieved sources do not support.

Grading runs as two independent passes. The grounding pass sees the question, the generated answer, and exactly the sources the system retrieved, and it scores groundedness, citation accuracy, and completeness against those sources only. The correctness pass compares the answer to the expert reference in a separate call, without the sources. Keeping the views apart stops agreement with a reference from masking an unsupported claim.

Both run at temperature 0, scores clamp to a 0 to 2 rubric, and a malformed judge response is recorded as a failure. It is never coerced into a zero.

## Scale, cost, and operations

### How large a corpus can this handle?

The graph is sized for the hundreds to low tens of thousands of entities a domain corpus produces, and the methodology names millions of chunks as the scale at which you would outgrow one database.

Two things hold that up. Vector search stays indexed because the default dimension sits inside pgvector's HNSW limit, so it does not degrade into a full scan as the corpus grows. And graph traversal is a two-hop walk over indexed foreign keys, which is bounded work. The decision record's own revisit condition is a corpus reaching millions of entities, or a product that needs three or more hops at query time.

If you get there, the seam is clean: the graph layer is one stage behind the retrieval facade, so swapping in a graph engine means reimplementing that one stage.

### What does it cost to run?

Locally, nothing beyond your own machine and whatever model calls you make. Deployed, the database is the steady cost.

The Google Cloud deployment is one Cloud SQL instance with pgvector, one Cloud Run service for REST and MCP, and one Cloud Run job for migrations and ingestion. The database is what runs continuously, and the default `db-g1-small` tier is a few tens of dollars a month, so tear down experiments with `terraform destroy` when you are done.

Model cost is yours to control, and the profiles are the lever. `interactive` runs vector and keyword only, so the retrieval path costs one query embedding and caches it briefly. `deep` adds graph traversal and HyDE, which each call a generation model per query. There is no per-query agentic loop either way, so cost per question is predictable, and not a function of how hard the model decided the question was.

### What happens when a retrieval layer times out?

It contributes no candidates, the request continues, and the trace says what happened.

Each stage runs as its own task with its own database session and its own timeout. A slow or failing one records `timeout`, `error`, `empty`, `skipped`, or `disabled` in a per-stage trace, and the caller sees exactly what ran. Catching the exception and pretending the stage succeeded is the thing the design forbids, because a quietly weaker answer looks exactly like a strong one.

Traces are content-free by design. They carry stage, status, duration, and candidate counts, never query text, chunk text, or API keys, so they are always safe to log.

## Extending and adapting

### Can I add my own parser, reranker, or model provider?

Yes. Those are three of the five seams the kit is built to vary at.

| Need | Contract | Primary file |
|---|---|---|
| New document type | produce the shared parsed block model | `src/sci_rag/ingest/parsers.py` |
| New source system | produce `CorpusEntry` values | `src/sci_rag/ingest/manifest.py` |
| New post-fusion ranking | implement `Reranker` | `src/sci_rag/retrieve/rerank.py` |
| New embedding or generation model | implement `EmbeddingProvider` or `LLMClient` | `src/sci_rag/embed/`, `src/sci_rag/llm/` |
| New identity system | implement `AuthBackend` | `src/sci_rag/server/auth.py` |

Each seam comes with the evidence it expects, and for anything that changes ranking that means an ablation. [Extend the seams](extend.md) is the walkthrough.

### Is there a plugin system?

No, and that is deliberate. There is also no task queue, no cache service, no vector-store sidecar, and no graph database.

A small factory selects providers, so the supported set stays visible in one file. Adding a fourth generation provider means writing an adapter next to the three that ship, not registering anything. The cost is that you cannot drop in someone else's package without editing code; the benefit is that reading `get_llm()` tells you the whole truth about what this deployment can reach.

### Can I rename the Python package?

You can, but the kit deliberately does not, and derived projects keep the `sci_rag` import path.

Renaming buys nothing functional and costs you the ability to diff your project against the upstream template and pull improvements from it. That benefit is live: the generator fetches this repository byte for byte, so your tree and upstream's stay comparable. `scripts/init_domain.py` handles the cosmetic rebranding, meaning project name, description, and a seed-question reset, without touching the import path. `sci-rag init` includes the same operation in its broader setup flow.

### How much of this should I change?

As much as you need to. It is your copy.

The parts built to be replaced are `domain/` (ontology, prompts, retrieval tuning, evaluation questions), the corpus manifest, and `.env`. Most projects never need more than those. Beyond them, the five seams above are where real projects vary, and changing something outside them is a normal code change in a repository you own.

Two things are worth keeping if you can. Run an evaluation before and after a retrieval change, because the ablation is what turns a hunch into a decision. And keep the rights scope inside every layer's SQL, because that boundary is a correctness property, and it is the easiest thing here to break by accident.

## The project

### Is this production ready? What does 0.x mean?

It is alpha, and 0.x here promises something specific.

Minor releases may break APIs, and the changelog says so under a "Breaking" heading with a migration note. Patch releases do not break anything. Database schema changes ship as Alembic migrations that run forward from any prior release. Evaluation report JSON is additive, and domain profiles written for an older 0.x keep working.

The compatibility promise covers five surfaces: the documented top-level Python exports, the CLI command surface, the REST contract under `/v1` plus the MCP tool names and schemas, the `domain/` directory format, and evaluation report JSON keys. Internal module paths may move in any minor release. [Versioning](VERSIONING.md) lists what 1.0 waits for, including two production deployments outside the maintainers' own.

### How do I cite it?

Cite the software title, version or exact Git commit, repository URL, and access date. There is no archival DOI yet, and you should not cite a placeholder as though an archive exists.

Pinning the commit matters especially during 0.x, because minor releases may break public interfaces. A software citation alone also does not identify a retrieval experiment, so report the corpus snapshot and digest, the license-scope rules, the model identifiers, the domain profile, the enabled layers, and the evaluation question set alongside it. [How to cite](citation.md) has the BibTeX and the full methods-section list.

### Who maintains it, and how are decisions made?

The Sustainability Software Lab team at Berkeley Lab maintains it, and decisions are made in the open at three levels.

Code-level decisions happen in pull requests and resolve by evidence: an ablation, a benchmark, or a failing test. Architecture decisions get a decision record. Direction-level proposals, meaning new subsystems and anything touching the five public surfaces, start as an RFC in GitHub Discussions and become a record plus issues when they converge.

What the project optimizes for is stated plainly: correct over clever, honest over impressive, evidence over authority. Reviewers are explicitly empowered to block anything that publishes an unmeasured claim. [Governance](GOVERNANCE.md) has the roles and the tie-break rule.
