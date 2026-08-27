---
template: home.html
title: Sci-RAG Kit
description: Build a citation-backed, evaluated scientific knowledge base from your own literature with one inspectable Postgres system.
hide:
  - navigation
  - toc
---

<section class="srag-home-hero" aria-labelledby="srag-hero-title" markdown>

<div class="srag-home-hero__glow" aria-hidden="true"></div>

<div class="srag-home-hero__inner md-grid" markdown>

<div class="srag-home-hero__copy" markdown>

<div class="srag-home-hero__brand" aria-hidden="true">
  <img
    class="srag-home-hero__logo srag-logo--light"
    src="assets/branding/full-logo/sci-rag-kit-full-color-transparent.png"
    alt=""
    width="2048"
    height="768"
  >
  <img
    class="srag-home-hero__logo srag-logo--dark"
    src="assets/branding/monochrome/sci-rag-kit-full-white-transparent.png"
    alt=""
    width="2048"
    height="768"
  >
</div>

<p class="srag-kicker">Scientific retrieval infrastructure</p>

# A DIY GraphRAG factory for scientific domains. { #srag-hero-title }

<p class="srag-home-hero__lede">Ingest your literature, preserve its provenance and rights, retrieve through five fused layers, generate cited answers, and evaluate the complete path.</p>

<div class="srag-home-hero__actions" markdown>
[Build your first knowledge base](quickstart.md){ .srag-button .srag-button--primary }
[Explore the architecture](architecture.md){ .srag-button .srag-button--secondary }
</div>

<p class="srag-home-hero__status">
  <span class="srag-status-dot" aria-hidden="true"></span>
  v0.2.0 · alpha · install by template or clone
</p>

</div>

<figure class="srag-home-hero__figure">
  <img
    src="assets/diagrams/pipeline.svg"
    alt="Scientific papers and reports flow through structure-aware ingestion into one Postgres database, then through five fused retrieval layers to cited answers and evaluation."
    width="1400"
    height="760"
  >
  <figcaption>One inspectable path from source document to evaluated answer.</figcaption>
</figure>

</div>

</section>

<section class="srag-home-section srag-home-quickstart" id="quickstart" markdown>

<div class="srag-home-section__head" markdown>

<p class="srag-kicker">Start without credentials</p>

## Inspect a working pipeline in about ten minutes

The bundled five-document corpus is synthetic, CC0, and small enough to run locally. The offline embedder shows the ingestion, ranking, and retrieval-evaluation mechanics without sending text to a model provider.

[Follow the guided quickstart](quickstart.md)

</div>

```console title="Terminal"
$ git clone https://github.com/sustainability-software-lab/sci-rag-kit.git
$ cd sci-rag-kit
$ make setup
$ SCI_RAG_EMBEDDING_PROVIDER=local-hash make demo
```

</section>

<section class="srag-home-section" id="capabilities" markdown>

<div class="srag-home-section__head" markdown>

<p class="srag-kicker">One coherent system</p>

## The pieces scientific RAG needs, already wired together

The kit makes a small set of explicit architectural bets, then exposes the evidence needed to judge whether those bets fit your field.

</div>

<div class="srag-capability-grid" markdown>

<div class="srag-capability" markdown>
<span class="srag-capability__mark">01</span>

### Structure-aware ingestion

PDF, Markdown, and text become chunks that retain section paths and intact tables. [Follow ingestion into storage](architecture.md#data-model).
</div>

<div class="srag-capability" markdown>
<span class="srag-capability__mark">02</span>

### Five-layer retrieval

Vector, keyword, graph, community, and HyDE candidates meet in one weighted fusion. [See the retrieval design](methodology.md).
</div>

<div class="srag-capability" markdown>
<span class="srag-capability__mark">03</span>

### Postgres-native graph

Vectors, full-text search, concepts, relationships, and source records live together. [Understand the decision](adr/0001-graph-in-postgres.md).
</div>

<div class="srag-capability" markdown>
<span class="srag-capability__mark">04</span>

### Rights-aware scope

License and metadata filters are enforced inside every eligible layer before ranking. [Trace the rights contract](evidence-and-rights.md).
</div>

<div class="srag-capability" markdown>
<span class="srag-capability__mark">05</span>

### Cited answers

Every answer is assembled from numbered evidence, with a refusal when nothing is in scope. [Use REST or MCP](api.md).
</div>

<div class="srag-capability" markdown>
<span class="srag-capability__mark">06</span>

### Honest evaluation

Ablations, confidence intervals, blind judging, calibration, and corpus fingerprints turn quality claims into artifacts. [Evaluate your pipeline](evaluation.md).
</div>

</div>

</section>

<section class="srag-home-section" id="repository" markdown>

<div class="srag-home-split" markdown>

<div markdown>
<p class="srag-kicker">Your copy, your system</p>

## Specialize one working repository

Sci-RAG Kit is not a code generator. Use the GitHub template, then make the checked-in `domain/` profile and corpus yours. The repository you can read is the application you run.

`domain/` is the deliberate specialization surface: ontology, prompts, retrieval tuning, and evaluation questions. The rest of the tree stays ordinary Python that you can inspect, test, and change.

[Tour the repository](tour.md) · [Bring your own domain](bring-your-own-domain.md)
</div>

<pre class="srag-home-tree" aria-label="Annotated repository tree"><code>your-sci-rag/
├── domain/           ← ontology, prompts, eval questions
├── data/             ← your source documents and manifests
├── src/sci_rag/      ← ingestion through serving
├── migrations/       ← Postgres + pgvector schema
├── tests/            ← offline unit and integration evidence
├── infra/terraform/  ← optional Cloud SQL + Cloud Run
└── docs/             ← methods, guides, API, decisions</code></pre>
</div>

</section>

<section class="srag-home-section" id="pathways" markdown>

<div class="srag-home-section__head" markdown>

<p class="srag-kicker">Start with your goal</p>

## Choose the shortest useful path

The site is organized by intent: learn the system, complete a task, or look up an exact interface.

</div>

<div class="srag-pathway-grid" markdown>

[<span class="srag-card__eyebrow">Run it</span><span class="srag-card__title">I want a working example</span><span class="srag-card__copy">Set up Postgres, ingest the CC0 fixture corpus, inspect retrieval, and serve the same tools over REST and MCP.</span>](quickstart.md){ .srag-card }

[<span class="srag-card__eyebrow">Understand it</span><span class="srag-card__title">I need the architecture and its reasons</span><span class="srag-card__copy">Read the software map first, then the methodology specification and decision records.</span>](architecture.md){ .srag-card }

[<span class="srag-card__eyebrow">Make it mine</span><span class="srag-card__title">I want to ingest my own literature</span><span class="srag-card__copy">Define your ontology, prompts, source manifest, and questions without inventing a second framework.</span>](bring-your-own-domain.md){ .srag-card }

[<span class="srag-card__eyebrow">Build a corpus</span><span class="srag-card__title">I need lawful open-access inputs</span><span class="srag-card__copy">Discover DOI candidates, review fail-closed rights resolution, then download verified direct PDFs into an ingestible manifest.</span>](campaigns.md){ .srag-card }

[<span class="srag-card__eyebrow">Prove it</span><span class="srag-card__title">I need to evaluate retrieval and answers</span><span class="srag-card__copy">Run layer ablations, compare reports, calibrate the judge, and keep the corpus fingerprint attached.</span>](evaluation.md){ .srag-card }

</div>

</section>

<section class="srag-home-section" id="principles" markdown>

<div class="srag-home-split" markdown>

<div markdown>
<p class="srag-kicker">Design principles</p>

## Opinionated where reliability matters. Open at named seams.

No cache fleet, plug-in framework, graph sidecar, or invisible agent loop is hiding behind the quickstart. The defaults stay small enough to explain in a methods section.

[Read the methodology](methodology.md) · [See the extension seams](extend.md)
</div>

<div class="srag-principle-grid" markdown>

<div class="srag-capability" markdown>
### Preserve provenance

Source identity and section context survive ingestion, ranking, and citation.
</div>

<div class="srag-capability" markdown>
### Fail closed on rights

An empty license allowlist returns nothing. Unknown never means safe.
</div>

<div class="srag-capability" markdown>
### Make degradation visible

A timed-out layer becomes a trace, not a quietly weaker answer.
</div>

<div class="srag-capability" markdown>
### Earn complexity with evidence

Retrieval changes ship behind an ablation and stay only when measured.
</div>

</div>

</div>

</section>

<section class="srag-home-section srag-home-cta" markdown>

## Build your first scientific knowledge base

Start with the offline demo, then replace one surface at a time: corpus, domain model, evaluation questions, and credentials.

[Open the quickstart](quickstart.md){ .srag-button .srag-button--primary }
[Decide whether the kit fits](choosing-sci-rag-kit.md){ .srag-button .srag-button--secondary }

</section>
