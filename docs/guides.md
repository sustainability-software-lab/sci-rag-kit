---
title: Guides
description: Complete a specific task, from measuring quality to deploying and operating the service.
---

# Guides

Each guide starts from an outcome and assumes a finished [quickstart](quickstart.md). The reference section holds the exact commands, fields, and contracts.

<div class="srag-rows" markdown>

[<span class="srag-row__title">Evaluate your pipeline</span><span class="srag-row__copy">Score retrieval layer by layer, grade generated answers, compare two runs, and check the grader against human judgment.</span>](evaluation.md){ .srag-row }

[<span class="srag-row__title">Run a corpus campaign</span><span class="srag-row__copy">Find papers by topic or DOI list, resolve their rights, download the open-access PDFs, and screen them against stated criteria.</span>](campaigns.md){ .srag-row }

[<span class="srag-row__title">Run Postgres your way</span><span class="srag-row__copy">Docker, conda-forge, a system PostgreSQL or Postgres.app, or the optional Cloud SQL development helper.</span>](run-postgres.md){ .srag-row }

[<span class="srag-row__title">Operate a live corpus</span><span class="srag-row__copy">Back up, restore, snapshot, delete, and re-embed a corpus that keeps changing under a running service.</span>](operations.md){ .srag-row }

[<span class="srag-row__title">Deploy on Google Cloud</span><span class="srag-row__copy">Provision Cloud SQL and Cloud Run from the included Terraform and verify the running service.</span>](deploy-gcp.md){ .srag-row }

[<span class="srag-row__title">Extend the kit</span><span class="srag-row__copy">Add a parser, corpus collector, reranker, model provider, or authentication backend at one of the five supported boundaries.</span>](extend.md){ .srag-row }

</div>

Most readers arrive here with a corpus of their own already in the database, from [Bring your own domain](bring-your-own-domain.md). [Evaluate your pipeline](evaluation.md) comes first, before any retrieval setting changes. The other guides apply when the need arises.
