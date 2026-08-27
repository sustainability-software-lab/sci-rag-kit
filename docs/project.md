---
title: Project
description: Understand Sci-RAG Kit's status, principles, roadmap, governance, decisions, releases, and contribution process.
---

# Project

Sci-RAG Kit is alpha software with an explicit compatibility promise, an evidence-first roadmap, and short decision records for the architectural bets that shape every deployment.

<div class="srag-card-grid" markdown>

[<span class="srag-card__eyebrow">Direction</span><span class="srag-card__title">Roadmap</span><span class="srag-card__copy">See what shipped in v0.2, what is planned for scientific campaigns, and which launch decisions remain human-owned.</span>](ROADMAP.md){ .srag-card }

[<span class="srag-card__eyebrow">Compatibility</span><span class="srag-card__title">Versioning</span><span class="srag-card__copy">Learn which five public surfaces hold within 0.x and what evidence is required before a 1.0 promise.</span>](VERSIONING.md){ .srag-card }

[<span class="srag-card__eyebrow">Decisions</span><span class="srag-card__title">Architecture records</span><span class="srag-card__copy">Read why the graph lives in Postgres, embeddings are 1536-dimensional, and the repository is a live template.</span>](adr/0001-graph-in-postgres.md){ .srag-card }

[<span class="srag-card__eyebrow">Participation</span><span class="srag-card__title">Governance and contributing</span><span class="srag-card__copy">Understand how proposals become evidence, decisions, tests, documentation, and releases.</span>](GOVERNANCE.md){ .srag-card }

</div>

## Design principles

- **Correct over clever.** A small explicit system is easier to inspect and defend.
- **Evidence over authority.** Retrieval changes bring ablations; evaluation claims bring corpus and model provenance.
- **Honest over impressive.** Missing evidence produces a refusal, a degraded layer produces a trace, and a planned feature stays labeled planned.
- **One operational story.** Postgres holds text, vectors, full-text search, and graph rows so teams operate one primary data system.
- **Named seams, not a plug-in framework.** Extend the few contracts that correspond to real variation, and keep everything else readable.

Continue with the [decision records](adr/0001-graph-in-postgres.md), [changelog](changelog.md), or [contribution guide](contributing.md).
