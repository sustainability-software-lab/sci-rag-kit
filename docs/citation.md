---
title: How to cite
description: Cite the Sci RAG Kit software today and understand the archival DOI boundary for future releases.
---

# How to cite Sci RAG Kit

Sci RAG Kit does not currently publish an archival DOI or a `CITATION.cff`. Minting a Zenodo DOI is a maintainer-owned launch decision recorded in the [roadmap](ROADMAP.md#launch-gated-decisions-owner-maintainer-not-automation). Do not cite a placeholder as if an archive exists.

For work performed with the current release, cite the software title, version or exact Git commit, repository URL, and access date. Pinning the commit is especially important during 0.x because minor releases may break public interfaces.

## Suggested BibTeX

```bibtex
@software{sci_rag_kit_2026,
  author  = {{Sci RAG Kit contributors}},
  title   = {Sci RAG Kit: A DIY GraphRAG factory for scientific domains},
  year    = {2026},
  version = {0.3.0},
  url     = {https://github.com/sustainability-software-lab/sci-rag-kit},
  license = {BSD-3-Clause}
}
```

Add `note = {Git commit ...; accessed YYYY-MM-DD}` when the exact code state matters. If you modified the template substantially, cite both Sci RAG Kit and your derived repository or archived release so readers can reproduce the deployed method.

## What else to report in a methods section

A software citation alone does not identify a RAG experiment. Also report:

- the corpus snapshot name and digest;
- source-selection and license-scope rules;
- Crossref enrichment time and known-retraction review policy;
- embedding and generation model identifiers;
- the domain profile and retrieval configuration commit;
- enabled layers, routing profile, and reranker state;
- evaluation question-set version and judge calibration evidence.

Evaluation reports and named corpus snapshots already record most of this provenance. See [Evaluate your pipeline](evaluation.md) and [Evidence and rights](evidence-and-rights.md).
