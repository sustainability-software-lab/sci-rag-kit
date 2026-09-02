---
title: Guides
description: Complete a specific task, from measuring quality to deploying and operating the service.
---

# Guides

Each guide starts from an outcome and assumes you have finished the [quickstart](quickstart.md). Use the reference section when you need an exact command, field, or contract.

<div class="srag-rows" markdown>

[<span class="srag-row__title">Evaluate your pipeline</span><span class="srag-row__copy">Score retrieval layer by layer, grade generated answers, compare two runs, and check the grader against human judgment.</span>](evaluation.md){ .srag-row }

[<span class="srag-row__title">Run a corpus campaign</span><span class="srag-row__copy">Find papers by topic or DOI list, resolve their rights, download the open-access PDFs, and screen them against your criteria.</span>](campaigns.md){ .srag-row }

[<span class="srag-row__title">Run Postgres your way</span><span class="srag-row__copy">Choose Docker, conda-forge, a system PostgreSQL or Postgres.app, or the optional Cloud SQL development helper.</span>](run-postgres.md){ .srag-row }

[<span class="srag-row__title">Operate a live corpus</span><span class="srag-row__copy">Back up, restore, snapshot, delete, and re-embed a corpus that keeps changing under a running service.</span>](operations.md){ .srag-row }

[<span class="srag-row__title">Deploy on Google Cloud</span><span class="srag-row__copy">Provision Cloud SQL and Cloud Run from the included Terraform and verify the running service.</span>](deploy-gcp.md){ .srag-row }

[<span class="srag-row__title">Extend the kit</span><span class="srag-row__copy">Add a parser, corpus collector, reranker, model provider, or authentication backend at one of the five supported boundaries.</span>](extend.md){ .srag-row }

</div>

Most readers arrive here with their own corpus in the database, from [Bring your own domain](bring-your-own-domain.md). Read [Evaluate your pipeline](evaluation.md) first, before you change any retrieval setting. The other guides are for when you need them.
