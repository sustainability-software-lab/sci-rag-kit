---
template: home.html
title: Sci RAG Kit
description: Retrieval-augmented generation, built around your scientific domain.
hide:
  - navigation
  - toc
---

<section class="srag-home-section srag-home-masthead" markdown>

<div class="srag-home-masthead__brand">
  <img class="srag-home-masthead__logo srag-logo--light" src="assets/branding/full-logo/sci-rag-kit-full-color-transparent.png" alt="Sci RAG Kit" width="2048" height="768">
  <img class="srag-home-masthead__logo srag-logo--dark" src="assets/branding/monochrome/sci-rag-kit-full-white-transparent.png" alt="Sci RAG Kit" width="2048" height="768">
</div>

# Retrieval-augmented generation, built around your scientific domain.

<div class="srag-home-masthead__lede" markdown>

Sci RAG Kit provides a blueprint for custom RAG development,
from document ingestion
to retrieval, and evaluation. Fully
extensible and ready to scale. Shipped with API and MCP endpoints included
for serving locally or in production.

</div>

</section>

<section class="srag-home-section" markdown>

<figure class="srag-home-figure">
  <img
    src="assets/diagrams/pipeline.svg"
    alt="Scientific papers and reports flow through structure-aware ingestion into one Postgres database, then through five fused retrieval layers to cited answers and evaluation."
    width="1360"
    height="600"
  >
  <figcaption>End-to-end RAG architecture that ships with every new Sci RAG Kit project.</figcaption>
</figure>

</section>

<section class="srag-home-section" id="demo" markdown>

<!-- BEGIN KIT ONBOARDING: removed from generated projects by sci_rag.scaffold.apply -->

## Start a project

Get up and running with two terminal commands

```console title="Terminal"
$ pipx install sci-rag-kit
$ sci-rag new
```

The setup wizard will guide you through a series of
questions to initialize your project and automatically populate configuration
files for you

Quick mode asks for six setup decisions, plus the credential value required by
the selected mode, and supplies defaults for everything else. Choose Offline if
you do not want a model credential, or Advanced to reach every applicable option.

<div id="srag-cast" class="srag-cast" data-cast="assets/casts/sci-rag-new.cast" data-autoplay="true" aria-label="Recorded sci-rag new session"></div>
<small> (A full trace of this terminal session can be found [below](#example))</small>

Want to look first? [Other ways in](quickstart.md#other-ways-in) covers a clone, the GitHub template, `sci-rag init`, and the dev container.

Want to follow a step-by-step tutorial to get started? Follow our
[Quickstart](quickstart.md) guide.
It will take you from installation and setup through document ingestion,
retrieval, and
benchmarking, all on your local machine.

<!-- END KIT ONBOARDING -->

</section>

<section class="srag-home-section" id="components" markdown>

## What's in the kit?

<div class="srag-defs" markdown>

Structure-aware ingestion: PDF, Markdown, and text become chunks that retain
section paths and intact tables. [Follow ingestion into
storage](architecture.md#data-model).

Five-layer retrieval: Vector, keyword, graph, community, and HyDE candidates
meet in one weighted fusion. [See the retrieval design](methodology.md).

Postgres-native graph: Vectors, full-text search, concepts, relationships,
and source records live together. [Read the decision
record](adr/0001-graph-in-postgres.md).

Rights-aware scope: License and metadata filters are enforced inside every
eligible layer before ranking. [Trace the rights
contract](evidence-and-rights.md).

Cited answers: Every answer is assembled from numbered evidence, with a
refusal when nothing is in scope. [Use REST or MCP](api.md).

Evaluation: Ablations, confidence intervals, blind judging, calibration, and
corpus fingerprints turn quality claims into artifacts. [Evaluate your
pipeline](evaluation.md).

</div>

</section>

<section class="srag-home-section" id="repository" markdown>

## Config-first Customization

Sci RAG Kit handles customization primarily through configuration files.

<!-- BEGIN KIT ONBOARDING -->
First, install the kit on the command line with: `pipx install sci-rag-kit`.
Then running `sci-rag new` will update the config files in
place based on your responses to the setup questions.
<!-- END KIT ONBOARDING -->

`domain/` is where your domain-definition files live:
ontology, prompts, retrieval tuning, and
evaluation questions.

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

[<span class="srag-row__title">Run a corpus campaign</span><span class="srag-row__copy">Discover DOI candidates, review fail-closed rights resolution, then download verified direct PDFs into an ingestible manifest.</span>](campaigns.md){ .srag-row }

[<span class="srag-row__title">Evaluate your pipeline</span><span class="srag-row__copy">Run layer ablations, compare reports, calibrate the judge, and keep the corpus fingerprint attached.</span>](evaluation.md){ .srag-row }

[<span class="srag-row__title">FAQ</span><span class="srag-row__copy">Our most commonly asked questions and answers.</span>](faq.md){ .srag-row }

[<span class="srag-row__title">Choosing Sci RAG Kit</span><span class="srag-row__copy">Compare the kit with LightRAG, PaperQA2, LlamaIndex, and Microsoft GraphRAG before you commit to it.</span>](choosing-sci-rag-kit.md){ .srag-row }

</div>

</section>

<!-- BEGIN KIT ONBOARDING -->

<section class="srag-home-section" id="example" markdown>

## Example CLI Setup Wizard Session

The recommended Quick session above, in full. `scripts/render_cast.py` builds it by driving the real wizard, so it cannot drift from what `sci-rag new` actually asks. Regenerate with `make cast`. `make docs` fails if you forget.

<!-- BEGIN GENERATED TRANSCRIPT: scripts/render_cast.py -->

<div class="highlight srag-term">
<span class="filename">Terminal</span>
<pre><code><span class="srag-term__line srag-term__line--cmd"><span class="srag-term__prompt">$ </span><span class="srag-term__cmd">pipx install sci-rag-kit</span></span>
<span class="srag-term__line srag-term__line--cmd"><span class="srag-term__prompt">$ </span><span class="srag-term__cmd">sci-rag new</span></span>
<span class="srag-term__line srag-term__line--select srag-term__break"><span class="srag-term__heading">Select Setup</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">1 - </span><span class="srag-term__choice">Quick - Six questions, sensible defaults for the rest</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">2 - </span><span class="srag-term__choice">Advanced - Every option, for when you know what you want</span></span>
<span class="srag-term__line srag-term__line--choose"><span class="srag-term__key">Choose from [1/2] (1):</span><span class="srag-term__value"> 1</span></span>
<span class="srag-term__line srag-term__line--prompt"><span class="srag-term__key">project_name</span><span class="srag-term__default"> (My Scientific KB):</span><span class="srag-term__value"> Membrane Materials KB</span></span>
<span class="srag-term__line srag-term__line--prompt"><span class="srag-term__key">description</span><span class="srag-term__default"> (A short description of your domain.):</span><span class="srag-term__value"> Membrane chemistry and performance for water treatment</span></span>
<span class="srag-term__line srag-term__line--prompt"><span class="srag-term__key">contact_email</span><span class="srag-term__default"> (Sent to OpenAlex, Crossref, and Unpaywall):</span><span class="srag-term__value"> you@lbl.gov</span></span>
<span class="srag-term__line srag-term__line--select srag-term__break"><span class="srag-term__heading">Select environment_manager</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">1 - </span><span class="srag-term__choice">uv</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">2 - </span><span class="srag-term__choice">pixi</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">3 - </span><span class="srag-term__choice">conda</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">4 - </span><span class="srag-term__choice">venv+pip</span></span>
<span class="srag-term__line srag-term__line--choose"><span class="srag-term__key">Choose from [1/2/3/4] (1):</span><span class="srag-term__value"> 1</span></span>
<span class="srag-term__line srag-term__line--select srag-term__break"><span class="srag-term__heading">Select credentials</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">1 - </span><span class="srag-term__choice">google_ai_studio</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">2 - </span><span class="srag-term__choice">vertex_ai</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">3 - </span><span class="srag-term__choice">offline</span></span>
<span class="srag-term__line srag-term__line--choose"><span class="srag-term__key">Choose from [1/2/3] (1):</span><span class="srag-term__value"> 1</span></span>
<span class="srag-term__line srag-term__line--prompt"><span class="srag-term__key">google_api_key</span><span class="srag-term__default"> ():</span><span class="srag-term__value"></span></span>
<span class="srag-term__line srag-term__line--select srag-term__break"><span class="srag-term__heading">Select corpus_source</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">1 - </span><span class="srag-term__choice">local_files</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">2 - </span><span class="srag-term__choice">openalex_topic</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">3 - </span><span class="srag-term__choice">doi_list</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">4 - </span><span class="srag-term__choice">demo_only</span></span>
<span class="srag-term__line srag-term__line--choose"><span class="srag-term__key">Choose from [1/2/3/4] (1):</span><span class="srag-term__value"> 1</span></span>
<span class="srag-term__line srag-term__line--output">Checking the credential with one small model request...</span>
<span class="srag-term__line srag-term__line--output">gemini-2.5-flash answered in 90 ms.</span>
<span class="srag-term__line srag-term__line--empty"></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  Drafting an ontology for &quot;Membrane chemistry and performance for water treatment&quot;...</span></span>
<span class="srag-term__line srag-term__line--empty"></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  Entity types      Membrane, Material, Contaminant, Process, Property, Application, Organization, Standard</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  Relation types    MADE_OF, REMOVES, HAS_PROPERTY, USED_IN, REQUIRES, COMPARED_WITH</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  Query classes     performance, fabrication, fouling, application</span></span>
<span class="srag-term__line srag-term__line--empty"></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  Accept this ontology? [y/n/redraft] (y):</span></span>
<span class="srag-term__line srag-term__line--empty"></span>
<span class="srag-term__line srag-term__line--section"><span class="srag-term__heading">Fetching sci-rag-kit for membrane-materials-kb...</span></span>
<span class="srag-term__line srag-term__line--empty"></span>
<span class="srag-term__line srag-term__line--section"><span class="srag-term__heading">Writing membrane-materials-kb/</span></span>
<span class="srag-term__line srag-term__line--empty"></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  removed                docs/planning/, scripts/cloud_postgres.py, infra/terraform/dev-database/</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  domain/domain.yaml     8 entity types, 6 relation types, 4 query classes</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  data/demo/eval_seed_questions.jsonl   ground truth for the demo corpus</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  domain/eval_seed_questions.jsonl   guided blank</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  .env                   google_ai_studio, gemini-3.6-flash, gemini-embedding-001</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  pyproject.toml         name, description, extras: none</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  Makefile               commands prefixed with `uv run`</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  docs/                  kit onboarding, player, and cast removed</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  Dockerfile             uv base image</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  .devcontainer/         ghcr.io/va-h/devcontainers-features/uv:1</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  rendered               6 files for uv</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  data/corpus.jsonl      commented field shape, ready for your documents</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  LICENSE                BSD-3-Clause</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  README.md              rewritten opening</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  git                    initialized, 1 commit</span></span>
<span class="srag-term__line srag-term__line--empty"></span>
<span class="srag-term__line srag-term__line--done"><span class="srag-term__heading">Done. Membrane Materials KB is yours. Next:</span></span>
<span class="srag-term__line srag-term__line--empty"></span>
<span class="srag-term__line srag-term__line--next"><span class="srag-term__cmd">  cd membrane-materials-kb</span></span>
<span class="srag-term__line srag-term__line--next"><span class="srag-term__cmd">  uv sync</span></span>
<span class="srag-term__line srag-term__line--next"><span class="srag-term__cmd">  uv run sci-rag doctor</span></span>
<span class="srag-term__line srag-term__line--next"><span class="srag-term__cmd">  uv run sci-rag draft manifest --folder data/raw</span></span>
<span class="srag-term__line srag-term__line--next"><span class="srag-term__cmd">  uv run sci-rag ingest --manifest data/corpus.jsonl</span></span>
<span class="srag-term__line srag-term__line--empty"></span>
<span class="srag-term__line srag-term__line--output">Then let a model draft the rest of your domain files:</span>
<span class="srag-term__line srag-term__line--empty"></span>
<span class="srag-term__line srag-term__line--next"><span class="srag-term__cmd">  uv run sci-rag draft ontology --from-corpus</span></span>
<span class="srag-term__line srag-term__line--next"><span class="srag-term__cmd">  uv run sci-rag draft questions --count 10</span></span>
<span class="srag-term__line srag-term__line--empty"></span>
<span class="srag-term__line srag-term__line--output">Each one proposes a file for you to review rather than writing one, and each also prints its prompt (--print-prompt) if you would rather paste it into an assistant you already have. Guide: docs/llm-assisted-setup.md</span>
<span class="srag-term__line srag-term__line--empty"></span>
<span class="srag-term__line srag-term__line--output">The walkthrough: docs/bring-your-own-domain.md</span>
</code></pre>
</div>

<details markdown>
<summary>Show the Advanced setup</summary>

<div class="srag-cast" data-cast="assets/casts/sci-rag-new-advanced.cast" aria-label="Recorded Advanced sci-rag new session"></div>

<div class="highlight srag-term">
<span class="filename">Terminal</span>
<pre><code><span class="srag-term__line srag-term__line--cmd"><span class="srag-term__prompt">$ </span><span class="srag-term__cmd">pipx install sci-rag-kit</span></span>
<span class="srag-term__line srag-term__line--cmd"><span class="srag-term__prompt">$ </span><span class="srag-term__cmd">sci-rag new</span></span>
<span class="srag-term__line srag-term__line--select srag-term__break"><span class="srag-term__heading">Select Setup</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">1 - </span><span class="srag-term__choice">Quick - Six questions, sensible defaults for the rest</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">2 - </span><span class="srag-term__choice">Advanced - Every option, for when you know what you want</span></span>
<span class="srag-term__line srag-term__line--choose"><span class="srag-term__key">Choose from [1/2] (1):</span><span class="srag-term__value"> 2</span></span>
<span class="srag-term__line srag-term__line--prompt"><span class="srag-term__key">project_name</span><span class="srag-term__default"> (My Scientific KB):</span><span class="srag-term__value"> Membrane Materials KB</span></span>
<span class="srag-term__line srag-term__line--prompt"><span class="srag-term__key">repo_name</span><span class="srag-term__default"> (membrane-materials-kb):</span><span class="srag-term__value"></span></span>
<span class="srag-term__line srag-term__line--prompt"><span class="srag-term__key">description</span><span class="srag-term__default"> (A short description of your domain.):</span><span class="srag-term__value"> Membrane chemistry and performance for water treatment</span></span>
<span class="srag-term__line srag-term__line--prompt"><span class="srag-term__key">author_name</span><span class="srag-term__default"> (Your name, lab, or organization):</span><span class="srag-term__value"> Berkeley Lab</span></span>
<span class="srag-term__line srag-term__line--prompt"><span class="srag-term__key">contact_email</span><span class="srag-term__default"> (Sent to OpenAlex, Crossref, and Unpaywall):</span><span class="srag-term__value"> you@lbl.gov</span></span>
<span class="srag-term__line srag-term__line--prompt"><span class="srag-term__key">python_version</span><span class="srag-term__default"> (3.12):</span><span class="srag-term__value"></span></span>
<span class="srag-term__line srag-term__line--select srag-term__break"><span class="srag-term__heading">Select environment_manager</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">1 - </span><span class="srag-term__choice">uv</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">2 - </span><span class="srag-term__choice">pixi</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">3 - </span><span class="srag-term__choice">conda</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">4 - </span><span class="srag-term__choice">venv+pip</span></span>
<span class="srag-term__line srag-term__line--choose"><span class="srag-term__key">Choose from [1/2/3/4] (1):</span><span class="srag-term__value"> 2</span></span>
<span class="srag-term__line srag-term__line--select srag-term__break"><span class="srag-term__heading">Select dependency_file</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">1 - </span><span class="srag-term__choice">pyproject.toml</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">2 - </span><span class="srag-term__choice">pixi.toml</span></span>
<span class="srag-term__line srag-term__line--choose"><span class="srag-term__key">Choose from [1/2] (1):</span><span class="srag-term__value"></span></span>
<span class="srag-term__line srag-term__line--select srag-term__break"><span class="srag-term__heading">Select credentials</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">1 - </span><span class="srag-term__choice">google_ai_studio</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">2 - </span><span class="srag-term__choice">vertex_ai</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">3 - </span><span class="srag-term__choice">offline</span></span>
<span class="srag-term__line srag-term__line--choose"><span class="srag-term__key">Choose from [1/2/3] (1):</span><span class="srag-term__value"> 1</span></span>
<span class="srag-term__line srag-term__line--prompt"><span class="srag-term__key">google_api_key</span><span class="srag-term__default"> ():</span><span class="srag-term__value"></span></span>
<span class="srag-term__line srag-term__line--select srag-term__break"><span class="srag-term__heading">Select embedding_provider</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">1 - </span><span class="srag-term__choice">google</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">2 - </span><span class="srag-term__choice">local-hash</span></span>
<span class="srag-term__line srag-term__line--choose"><span class="srag-term__key">Choose from [1/2] (1):</span><span class="srag-term__value"></span></span>
<span class="srag-term__line srag-term__line--prompt"><span class="srag-term__key">llm_model</span><span class="srag-term__default"> (gemini-3.6-flash):</span><span class="srag-term__value"></span></span>
<span class="srag-term__line srag-term__line--prompt"><span class="srag-term__key">embedding_model</span><span class="srag-term__default"> (gemini-embedding-001):</span><span class="srag-term__value"></span></span>
<span class="srag-term__line srag-term__line--prompt"><span class="srag-term__key">embedding_dim</span><span class="srag-term__default"> (1536):</span><span class="srag-term__value"></span></span>
<span class="srag-term__line srag-term__line--select srag-term__break"><span class="srag-term__heading">Select ontology</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">1 - </span><span class="srag-term__choice">draft_with_llm</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">2 - </span><span class="srag-term__choice">keep_demo_example</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">3 - </span><span class="srag-term__choice">blank</span></span>
<span class="srag-term__line srag-term__line--choose"><span class="srag-term__key">Choose from [1/2/3] (1):</span><span class="srag-term__value"> 1</span></span>
<span class="srag-term__line srag-term__line--select srag-term__break"><span class="srag-term__heading">Select corpus_source</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">1 - </span><span class="srag-term__choice">local_files</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">2 - </span><span class="srag-term__choice">openalex_topic</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">3 - </span><span class="srag-term__choice">doi_list</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">4 - </span><span class="srag-term__choice">demo_only</span></span>
<span class="srag-term__line srag-term__line--choose"><span class="srag-term__key">Choose from [1/2/3/4] (1):</span><span class="srag-term__value"> 2</span></span>
<span class="srag-term__line srag-term__line--prompt"><span class="srag-term__key">openalex_topic</span><span class="srag-term__default"> (your topic):</span><span class="srag-term__value"> polyamide membrane fouling</span></span>
<span class="srag-term__line srag-term__line--prompt"><span class="srag-term__key">max_results</span><span class="srag-term__default"> (100):</span><span class="srag-term__value"> 250</span></span>
<span class="srag-term__line srag-term__line--select srag-term__break"><span class="srag-term__heading">Select pdf_parser</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">1 - </span><span class="srag-term__choice">pypdf</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">2 - </span><span class="srag-term__choice">docling</span></span>
<span class="srag-term__line srag-term__line--choose"><span class="srag-term__key">Choose from [1/2] (1):</span><span class="srag-term__value"> 2</span></span>
<span class="srag-term__line srag-term__line--select srag-term__break"><span class="srag-term__heading">Select reranker</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">1 - </span><span class="srag-term__choice">none</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">2 - </span><span class="srag-term__choice">llm</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">3 - </span><span class="srag-term__choice">local_cross_encoder</span></span>
<span class="srag-term__line srag-term__line--choose"><span class="srag-term__key">Choose from [1/2/3] (1):</span><span class="srag-term__value"></span></span>
<span class="srag-term__line srag-term__line--select srag-term__break"><span class="srag-term__heading">Select include_terraform</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">1 - </span><span class="srag-term__choice">Yes</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">2 - </span><span class="srag-term__choice">No</span></span>
<span class="srag-term__line srag-term__line--choose"><span class="srag-term__key">Choose from [1/2] (1):</span><span class="srag-term__value"> 2</span></span>
<span class="srag-term__line srag-term__line--select srag-term__break"><span class="srag-term__heading">Select include_cloud_database</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">1 - </span><span class="srag-term__choice">Yes</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">2 - </span><span class="srag-term__choice">No</span></span>
<span class="srag-term__line srag-term__line--choose"><span class="srag-term__key">Choose from [1/2] (2):</span><span class="srag-term__value"></span></span>
<span class="srag-term__line srag-term__line--select srag-term__break"><span class="srag-term__heading">Select include_demo_corpus</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">1 - </span><span class="srag-term__choice">Yes</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">2 - </span><span class="srag-term__choice">No</span></span>
<span class="srag-term__line srag-term__line--choose"><span class="srag-term__key">Choose from [1/2] (1):</span><span class="srag-term__value"> 2</span></span>
<span class="srag-term__line srag-term__line--select srag-term__break"><span class="srag-term__heading">Select open_source_license</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">1 - </span><span class="srag-term__choice">BSD-3-Clause</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">2 - </span><span class="srag-term__choice">MIT</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">3 - </span><span class="srag-term__choice">Apache-2.0</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">4 - </span><span class="srag-term__choice">No license file</span></span>
<span class="srag-term__line srag-term__line--choose"><span class="srag-term__key">Choose from [1/2/3/4] (1):</span><span class="srag-term__value"></span></span>
<span class="srag-term__line srag-term__line--select srag-term__break"><span class="srag-term__heading">Select initialize_git</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">1 - </span><span class="srag-term__choice">Yes</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">2 - </span><span class="srag-term__choice">No</span></span>
<span class="srag-term__line srag-term__line--choose"><span class="srag-term__key">Choose from [1/2] (1):</span><span class="srag-term__value"></span></span>
<span class="srag-term__line srag-term__line--select srag-term__break"><span class="srag-term__heading">Select draft_domain_files</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">1 - </span><span class="srag-term__choice">Yes</span></span>
<span class="srag-term__line srag-term__line--choice"><span class="srag-term__choice-n">2 - </span><span class="srag-term__choice">No</span></span>
<span class="srag-term__line srag-term__line--choose"><span class="srag-term__key">Choose from [1/2] (1):</span><span class="srag-term__value"></span></span>
<span class="srag-term__line srag-term__line--output">Checking the credential with one small model request...</span>
<span class="srag-term__line srag-term__line--output">gemini-2.5-flash answered in 90 ms.</span>
<span class="srag-term__line srag-term__line--empty"></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  Drafting an ontology for &quot;Membrane chemistry and performance for water treatment&quot;...</span></span>
<span class="srag-term__line srag-term__line--empty"></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  Entity types      Membrane, Material, Contaminant, Process, Property, Application, Organization, Standard</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  Relation types    MADE_OF, REMOVES, HAS_PROPERTY, USED_IN, REQUIRES, COMPARED_WITH</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  Query classes     performance, fabrication, fouling, application</span></span>
<span class="srag-term__line srag-term__line--empty"></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  Accept this ontology? [y/n/redraft] (y):</span></span>
<span class="srag-term__line srag-term__line--empty"></span>
<span class="srag-term__line srag-term__line--section"><span class="srag-term__heading">Fetching sci-rag-kit for membrane-materials-kb...</span></span>
<span class="srag-term__line srag-term__line--empty"></span>
<span class="srag-term__line srag-term__line--section"><span class="srag-term__heading">Writing membrane-materials-kb/</span></span>
<span class="srag-term__line srag-term__line--empty"></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  removed                docs/planning/, infra/terraform/, scripts/cloud_postgres.py, infra/terraform/dev-database/, data/demo/, examples/</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  domain/domain.yaml     8 entity types, 6 relation types, 4 query classes</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  domain/eval_seed_questions.jsonl   guided blank</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  .env                   google_ai_studio, gemini-3.6-flash, gemini-embedding-001</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  pyproject.toml         name, description, extras: docling</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  Makefile               commands prefixed with `pixi run`, database defaults to conda-forge, no Docker needed</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  docs/                  kit onboarding, player, and cast removed</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  pyproject.toml          workspace, environments, tasks</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  Dockerfile             pixi base image</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  .devcontainer/         ghcr.io/prefix-dev/devcontainer-features/pixi:0</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  rendered               9 files for pixi</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  pixi.lock              created on first `pixi install`</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  data/campaigns/        openalex topic &quot;polyamide membrane fouling&quot;</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  LICENSE                BSD-3-Clause</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  README.md              rewritten opening</span></span>
<span class="srag-term__line srag-term__line--status"><span class="srag-term__status">  git                    initialized, 1 commit</span></span>
<span class="srag-term__line srag-term__line--empty"></span>
<span class="srag-term__line srag-term__line--done"><span class="srag-term__heading">Done. Membrane Materials KB is yours. Next:</span></span>
<span class="srag-term__line srag-term__line--empty"></span>
<span class="srag-term__line srag-term__line--next"><span class="srag-term__cmd">  cd membrane-materials-kb</span></span>
<span class="srag-term__line srag-term__line--next"><span class="srag-term__cmd">  pixi install</span></span>
<span class="srag-term__line srag-term__line--next"><span class="srag-term__cmd">  pixi run sci-rag doctor</span></span>
<span class="srag-term__line srag-term__line--next"><span class="srag-term__cmd">  make corpus</span></span>
<span class="srag-term__line srag-term__line--empty"></span>
<span class="srag-term__line srag-term__line--output">Then let a model draft the rest of your domain files:</span>
<span class="srag-term__line srag-term__line--empty"></span>
<span class="srag-term__line srag-term__line--next"><span class="srag-term__cmd">  pixi run sci-rag draft ontology --from-corpus</span></span>
<span class="srag-term__line srag-term__line--next"><span class="srag-term__cmd">  pixi run sci-rag draft questions --count 10</span></span>
<span class="srag-term__line srag-term__line--empty"></span>
<span class="srag-term__line srag-term__line--output">Each one proposes a file for you to review rather than writing one, and each also prints its prompt (--print-prompt) if you would rather paste it into an assistant you already have. Guide: docs/llm-assisted-setup.md</span>
<span class="srag-term__line srag-term__line--empty"></span>
<span class="srag-term__line srag-term__line--output">The walkthrough: docs/bring-your-own-domain.md</span>
</code></pre>
</div>

</details>

<!-- END GENERATED TRANSCRIPT -->

</section>

<!-- END KIT ONBOARDING -->

<section class="srag-home-section srag-home-footer" markdown>

<p class="srag-home-footer__meta">v0.4.1, alpha. Install with pipx.</p>

</section>
