---
title: Get started
description: Install Sci RAG Kit, run the demo corpus, and find the page that matches what you need next.
---

# Get started

These pages take a clean clone to a running knowledge base, then point at the reference or guide you need next.

<div class="srag-rows" markdown>

[<span class="srag-row__title">Quickstart</span><span class="srag-row__copy">Install the kit, ingest the synthetic CC0 corpus, inspect retrieval, and expose the same service over REST and MCP. About 10 minutes.</span>](quickstart.md){ .srag-row }

[<span class="srag-row__title">Tour the repository</span><span class="srag-row__copy">See what you specialize, what you run, and why this is a live template repository rather than a generator.</span>](tour.md){ .srag-row }

[<span class="srag-row__title">Choosing Sci RAG Kit</span><span class="srag-row__copy">Compare the kit honestly with LightRAG, PaperQA2, LlamaIndex, and Microsoft GraphRAG.</span>](choosing-sci-rag-kit.md){ .srag-row }

[<span class="srag-row__title">Troubleshooting</span><span class="srag-row__copy">Start from the symptom, run `sci-rag doctor`, and follow the specific check or recovery path.</span>](troubleshooting.md){ .srag-row }

</div>

## Recommended path

1. Run the [quickstart](quickstart.md) with the offline embedder.
2. Read the [repository tour](tour.md) before replacing the demo profile.
3. Follow [Bring your own domain](bring-your-own-domain.md) with a small, well-understood corpus, or use a [corpus campaign](campaigns.md) to discover candidates and build a fail-closed open-access manifest.
4. Review the campaign's rights distribution before ingestion, then run an [evaluation](evaluation.md) before changing retrieval weights or enabling the reranker.

If Postgres, credentials, or parsing gets in the way, do not guess from an empty result. Run `uv run sci-rag doctor`; the kit is designed to tell you which layer is missing.
