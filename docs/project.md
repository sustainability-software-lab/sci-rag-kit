---
title: Project
description: Status, principles, roadmap, governance, decision records, releases, and how to contribute.
---

# Project

Sci RAG Kit is alpha software. Its versioning policy states the current compatibility promise, the roadmap separates shipped work from plans, and decision records explain the architecture.

<div class="srag-rows" markdown>

[<span class="srag-row__title">Roadmap</span><span class="srag-row__copy">What shipped, what comes next, and which decisions stay with a maintainer.</span>](ROADMAP.md){ .srag-row }

[<span class="srag-row__title">Versioning</span><span class="srag-row__copy">Which five public surfaces hold within 0.x, and what a 1.0 promise waits for.</span>](VERSIONING.md){ .srag-row }

[<span class="srag-row__title">Decision records</span><span class="srag-row__copy">Why the graph lives in Postgres, embeddings are 1536-dimensional, and the repository is a live template.</span>](adr/0001-graph-in-postgres.md){ .srag-row }

[<span class="srag-row__title">Governance and contributing</span><span class="srag-row__copy">How proposals become evidence, decisions, tests, documentation, and releases.</span>](GOVERNANCE.md){ .srag-row }

</div>

## Design principles

- **Prefer explicit, inspectable designs.** A small system is easier to understand and defend.
- **Require evidence for quality claims.** Retrieval changes bring a before-and-after evaluation, and reports name their corpus and models.
- **Show uncertainty and failure.** Missing evidence produces a refusal, failed layers appear in traces, and planned features stay labeled planned.
- **Keep operational state in Postgres.** Text, vectors, full-text search, and graph rows share one data system.
- **Extend through named seams.** Five supported boundaries cover the places where projects vary without introducing a plug-in framework.

Read [Roadmap](ROADMAP.md) for planned work, [Versioning](VERSIONING.md) for the compatibility promise, and the [decision records](adr/0001-graph-in-postgres.md) for architectural reasoning. To contribute, start with [Contributing](contributing.md) and [Documentation style](STYLE.md).
