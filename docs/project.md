---
title: Project
description: Status, principles, roadmap, governance, decision records, releases, and how to contribute.
---

# Project

Sci RAG Kit is alpha software with a stated compatibility promise, a roadmap that lands features only with evidence, and short decision records for the architectural bets that shape every deployment.

<div class="srag-rows" markdown>

[<span class="srag-row__title">Roadmap</span><span class="srag-row__copy">What shipped, what comes next, and which decisions stay with a maintainer.</span>](ROADMAP.md){ .srag-row }

[<span class="srag-row__title">Versioning</span><span class="srag-row__copy">Which five public surfaces hold within 0.x, and what a 1.0 promise waits for.</span>](VERSIONING.md){ .srag-row }

[<span class="srag-row__title">Decision records</span><span class="srag-row__copy">Why the graph lives in Postgres, embeddings are 1536-dimensional, and the repository is a live template.</span>](adr/0001-graph-in-postgres.md){ .srag-row }

[<span class="srag-row__title">Governance and contributing</span><span class="srag-row__copy">How proposals become evidence, decisions, tests, documentation, and releases.</span>](GOVERNANCE.md){ .srag-row }

</div>

## Design principles

- **Correct over clever.** A small explicit system is easier to inspect and defend.
- **Evidence over authority.** Retrieval changes bring a before-and-after evaluation. Quality claims name their corpus and models.
- **Honest over impressive.** Missing evidence produces a refusal, a failed layer produces a visible trace, and a planned feature stays labeled planned.
- **One operational story.** Postgres holds text, vectors, full-text search, and graph rows, so a team operates one data system.
- **Named seams, not a plug-in framework.** The kit exposes five boundaries where real projects vary and keeps everything else readable.

Read [Roadmap](ROADMAP.md) for where the project is going, [Versioning](VERSIONING.md) for what's guaranteed to remain stable, and the [decision records](adr/0001-graph-in-postgres.md) for why the shape is the shape. To contribute, start with [Contributing](contributing.md) and [Documentation style](STYLE.md).
