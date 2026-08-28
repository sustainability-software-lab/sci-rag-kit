---
template: home.html
title: Sci RAG Kit
description: Retrieval-augmented generation over scientific document collections, on one Postgres database.
hide:
  - navigation
  - toc
---

<section class="srag-home-section srag-home-masthead" markdown>

<div class="srag-home-masthead__brand">
  <img class="srag-home-masthead__logo srag-logo--light" src="assets/branding/full-logo/sci-rag-kit-full-color-transparent.png" alt="Sci-RAG Kit" width="2048" height="768">
  <img class="srag-home-masthead__logo srag-logo--dark" src="assets/branding/monochrome/sci-rag-kit-full-white-transparent.png" alt="Sci-RAG Kit" width="2048" height="768">
</div>

# Retrieval-augmented generation over scientific document collections, on one Postgres database

<p class="srag-home-masthead__lede">A template repository that ingests your literature, keeps provenance and rights attached, retrieves through five fused layers, generates cited answers, and evaluates the whole path.</p>

<p class="srag-home-masthead__meta">v0.2.0, alpha, BSD-3-Clause. Install by GitHub template or clone.</p>

</section>

<section class="srag-home-section" markdown>

<figure class="srag-home-figure">
  <img
    src="assets/diagrams/pipeline.svg"
    alt="Scientific papers and reports flow through structure-aware ingestion into one Postgres database, then through five fused retrieval layers to cited answers and evaluation."
    width="1360"
    height="600"
  >
  <figcaption>One path from source document to evaluated answer.</figcaption>
</figure>

</section>

<section class="srag-home-section" id="demo" markdown>

## Run the demo

The bundled five-document corpus is synthetic, CC0, and small enough to run locally. The offline embedder exercises ingestion, ranking, and retrieval evaluation without sending text to a model provider, so no credentials are required.

```console title="Terminal"
$ git clone https://github.com/sustainability-software-lab/sci-rag-kit.git
$ cd sci-rag-kit
$ make setup
$ SCI_RAG_EMBEDDING_PROVIDER=local-hash make demo
```

[Quickstart](quickstart.md)

</section>

<section class="srag-home-section" id="components" markdown>

## Components

<div class="srag-defs" markdown>

Structure-aware ingestion
:   PDF, Markdown, and text become chunks that retain section paths and intact tables. [Follow ingestion into storage](architecture.md#data-model).

Five-layer retrieval
:   Vector, keyword, graph, community, and HyDE candidates meet in one weighted fusion. [See the retrieval design](methodology.md).

Postgres-native graph
:   Vectors, full-text search, concepts, relationships, and source records live together. [Read the decision record](adr/0001-graph-in-postgres.md).

Rights-aware scope
:   License and metadata filters are enforced inside every eligible layer before ranking. [Trace the rights contract](evidence-and-rights.md).

Cited answers
:   Every answer is assembled from numbered evidence, with a refusal when nothing is in scope. [Use REST or MCP](api.md).

Evaluation
:   Ablations, confidence intervals, blind judging, calibration, and corpus fingerprints turn quality claims into artifacts. [Evaluate your pipeline](evaluation.md).

</div>

</section>

<section class="srag-home-section" id="repository" markdown>

## One repository, specialized

Sci-RAG Kit is not a code generator. Use the GitHub template, then make the checked-in `domain/` profile and corpus yours. The repository you can read is the application you run.

`domain/` is the specialization surface: ontology, prompts, retrieval tuning, and evaluation questions. The rest of the tree stays ordinary Python that you can inspect, test, and change.

<pre class="srag-home-tree" aria-label="Annotated repository tree"><code>your-sci-rag/
├── domain/           ontology, prompts, eval questions
├── data/             your source documents and manifests
├── src/sci_rag/      ingestion through serving
├── migrations/       Postgres and pgvector schema
├── tests/            offline unit and integration evidence
├── infra/terraform/  optional Cloud SQL and Cloud Run
└── docs/             methods, guides, API, decisions</code></pre>

[Tour the repository](tour.md) · [Bring your own domain](bring-your-own-domain.md)

</section>

<section class="srag-home-section" id="start" markdown>

## Where to start

<div class="srag-rows" markdown>

[<span class="srag-row__title">Quickstart</span><span class="srag-row__copy">Set up Postgres, ingest the CC0 fixture corpus, inspect retrieval, and serve the same tools over REST and MCP.</span>](quickstart.md){ .srag-row }

[<span class="srag-row__title">Architecture</span><span class="srag-row__copy">Read the software map first, then the methodology specification and the decision records.</span>](architecture.md){ .srag-row }

[<span class="srag-row__title">Bring your own domain</span><span class="srag-row__copy">Define your ontology, prompts, source manifest, and questions without inventing a second framework.</span>](bring-your-own-domain.md){ .srag-row }

[<span class="srag-row__title">Discover a corpus</span><span class="srag-row__copy">Discover DOI candidates, review fail-closed rights resolution, then download verified direct PDFs into an ingestible manifest.</span>](campaigns.md){ .srag-row }

[<span class="srag-row__title">Evaluate your pipeline</span><span class="srag-row__copy">Run layer ablations, compare reports, calibrate the judge, and keep the corpus fingerprint attached.</span>](evaluation.md){ .srag-row }

[<span class="srag-row__title">Choosing Sci-RAG Kit</span><span class="srag-row__copy">Compare the kit with LightRAG, PaperQA2, LlamaIndex, and Microsoft GraphRAG before you commit to it.</span>](choosing-sci-rag-kit.md){ .srag-row }

</div>

</section>

<section class="srag-home-section" id="principles" markdown>

## Design principles

<div class="srag-defs" markdown>

Preserve provenance
:   Source identity and section context survive ingestion, ranking, and citation.

Fail closed on rights
:   An empty license allowlist returns nothing. Unknown never means safe.

Make degradation visible
:   A timed-out layer becomes a trace, not a quietly weaker answer.

Earn complexity with evidence
:   Retrieval changes ship behind an ablation and stay only when measured.

</div>

No cache fleet, plug-in framework, graph sidecar, or hidden agent loop sits behind the quickstart. The defaults stay small enough to describe in a methods section. [Read the methodology](methodology.md) · [See the extension seams](extend.md)

</section>
