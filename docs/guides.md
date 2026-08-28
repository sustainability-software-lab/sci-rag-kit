---
title: Guides
description: Complete a specific Sci RAG Kit task, from configuring your domain to deploying and operating the service.
---

# Guides

Each guide starts from an outcome. Use the reference section when you need an exact command, field, or contract.

<div class="srag-rows" markdown>

[<span class="srag-row__title">Bring your own domain</span><span class="srag-row__copy">Replace the ontology, prompts, source manifest, and seed questions while keeping the pipeline testable.</span>](bring-your-own-domain.md){ .srag-row }

[<span class="srag-row__title">LLM-assisted setup</span><span class="srag-row__copy">Draft the ontology, manifest, seed questions, and prompts with a model, or with any assistant by copy-paste, and keep drafted ground truth labeled as such.</span>](llm-assisted-setup.md){ .srag-row }

[<span class="srag-row__title">Run a corpus campaign</span><span class="srag-row__copy">Discover DOI candidates, resolve explicit rights through Unpaywall, and download only verified direct PDFs into a manifest.</span>](campaigns.md){ .srag-row }

[<span class="srag-row__title">Evaluate your pipeline</span><span class="srag-row__copy">Run retrieval ablations and judged-answer evaluation, compare reports, and calibrate the judge.</span>](evaluation.md){ .srag-row }

[<span class="srag-row__title">Extend the seams</span><span class="srag-row__copy">Add a parser, corpus collector, reranker, model provider, or authentication backend without creating a plug-in framework.</span>](extend.md){ .srag-row }

[<span class="srag-row__title">Operate a live corpus</span><span class="srag-row__copy">Back up, restore, snapshot, delete, garbage-collect, and re-embed a changing corpus.</span>](operations.md){ .srag-row }

[<span class="srag-row__title">Deploy on Google Cloud</span><span class="srag-row__copy">Provision Cloud SQL and Cloud Run from the included Terraform and verify the running service.</span>](deploy-gcp.md){ .srag-row }

[<span class="srag-row__title">Run Postgres your way</span><span class="srag-row__copy">Get a server with pgvector using Docker, conda-forge, or one you already run, and know which path is yours.</span>](run-postgres.md){ .srag-row }

</div>

Most people arrive here after the quickstart, wanting their own corpus in the
database. Take them in this order: [Bring your own domain](bring-your-own-domain.md)
for the shape of the work, [LLM-assisted setup](llm-assisted-setup.md) to draft
the four domain files against your documents, then
[Evaluate your pipeline](evaluation.md) before you change a single retrieval
weight. The other four guides are there when you need them, and not before.
