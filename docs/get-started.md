---
title: Get started
description: Choose the shortest path from a clean clone to an inspectable Sci-RAG Kit knowledge base.
---

# Get started

Get a working system first, then decide how much of its architecture you need to understand or change.

<div class="srag-card-grid" markdown>

[<span class="srag-card__eyebrow">10 minutes</span><span class="srag-card__title">Quickstart</span><span class="srag-card__copy">Install the kit, ingest the synthetic CC0 corpus, inspect retrieval, and expose the same service over REST and MCP.</span>](quickstart.md){ .srag-card }

[<span class="srag-card__eyebrow">Orientation</span><span class="srag-card__title">Tour the repository</span><span class="srag-card__copy">See what you specialize, what you run, and why this is a live template repository rather than a generator.</span>](tour.md){ .srag-card }

[<span class="srag-card__eyebrow">Decision</span><span class="srag-card__title">Choosing Sci-RAG Kit</span><span class="srag-card__copy">Compare the kit honestly with LightRAG, PaperQA2, LlamaIndex, and Microsoft GraphRAG.</span>](choosing-sci-rag-kit.md){ .srag-card }

[<span class="srag-card__eyebrow">When it differs</span><span class="srag-card__title">Troubleshooting</span><span class="srag-card__copy">Start from the symptom, run `sci-rag doctor`, and follow the specific check or recovery path.</span>](troubleshooting.md){ .srag-card }

</div>

## Recommended path

1. Run the [quickstart](quickstart.md) with the offline embedder.
2. Read the [repository tour](tour.md) before replacing the demo profile.
3. Follow [Bring your own domain](bring-your-own-domain.md) with a small, well-understood corpus, or use a [corpus campaign](campaigns.md) to discover candidates and build a fail-closed open-access manifest.
4. Review the campaign's rights distribution before ingestion, then run an [evaluation](evaluation.md) before changing retrieval weights or enabling the reranker.

If Postgres, credentials, or parsing gets in the way, do not guess from an empty result. Run `uv run sci-rag doctor`; the kit is designed to tell you which layer is missing.
