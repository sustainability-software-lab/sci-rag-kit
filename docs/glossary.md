---
title: Glossary
description: Definitions for the retrieval, graph, evidence, evaluation, and operations terms used throughout Sci-RAG Kit.
---

# Glossary

These definitions describe how the project uses each term. They are intentionally narrower than every use in the broader RAG literature.

## Retrieval and generation

**Ablation**
: A controlled evaluation that disables or changes one retrieval component so its measured contribution can be compared with the baseline.

**Answer grounding**
: The degree to which claims in a generated answer are supported by the exact source passages supplied to the model.

**Candidate pool**
: The bounded items returned by one retrieval layer before fusion, or the wider fused set presented to a reranker.

**Chunk**
: The smallest stored and ranked text unit. A chunk retains its document identity, order, section path, table flag, embedding, and version stamp.

**Deep profile**
: The retrieval profile intended for offline or agent use. It enables the model-dependent layers and uses a longer per-stage timeout.

**Embedding**
: A fixed-length numeric vector representing text for similarity search. The default Google embedding is truncated and normalized to 1536 dimensions.

**Fusion**
: Combining ranked lists from several retrieval layers. Sci-RAG Kit uses weighted reciprocal rank fusion once per request.

**HyDE**
: Hypothetical Document Embeddings. A model writes the kind of passage that would answer the query; the system embeds that passage and searches near it.

**Interactive profile**
: The low-latency profile centered on vector and keyword retrieval, with shorter stage timeouts.

**RAG**
: Retrieval-augmented generation. Evidence is retrieved from a corpus and supplied to a generator so the answer can be grounded in those sources.

**Reciprocal rank fusion (RRF)**
: A method that scores an item from its positions in multiple ranked lists rather than comparing incompatible raw layer scores.

**Reranker**
: A post-fusion component that reads the query and candidate text, then reorders a wider pool. It is off until an ablation justifies its cost.

**Retrieval layer**
: One independent way to propose evidence. The five layers are vector, keyword, graph, community, and HyDE.

**Retrieval scope**
: The rights and metadata constraints a caller applies before ranking, including license, source, year, author, journal, and DOI exclusions.

## Graph and corpus

**Community**
: A deterministic cluster of related knowledge-graph entities with a precomputed model summary and embedding.

**Corpus fingerprint**
: Counts and embedding versions recorded on evaluation output so changes to the indexed knowledge base remain visible.

**Corpus campaign**
: A resumable workflow that discovers DOI candidates, resolves explicit open-access rights, downloads verified direct PDFs, and writes an ingestible manifest without inferring a license from availability alone.

**Corpus snapshot**
: A named, immutable record of per-document content hashes plus one digest, model versions, counts, and Git commit.

**Entity**
: A canonical named concept extracted under one of the types declared in `domain/domain.yaml`, with retained source aliases and pointers to the chunks and documents that support it.

**Knowledge graph**
: Typed entities and directed relationships stored as ordinary Postgres rows. It is a graph of domain concepts, not a second database.

**Known retraction**
: A document for which an applied Crossref enrichment response contains an explicit retraction assertion. Missing enrichment is not treated as proof that a work is current.

**Ontology**
: The allowed entity and relationship types for one scientific domain, expressed in `domain/domain.yaml`.

**Provenance**
: The identity and context needed to trace evidence back to its source, including document metadata, chunk section path, and graph evidence pointers.

**Relationship confidence**
: A calibrated knowledge-graph edge score: 1.0 for a direct statement, 0.7 for a strong implication, and 0.4 for an inference across sentences. Repeated extraction retains the highest observed score for the same typed edge.

**Source bucket**
: An operator-defined manifest label such as `journal_papers` or `agency_reports`, usable as a retrieval allowlist.

## Evaluation and operations

**Blind judge pass**
: Grounding evaluation in which the judge sees the question, generated answer, and retrieved evidence, but not the expert reference answer.

**Calibration**
: Comparison of model-judge labels with human labels. The project reports Cohen's kappa and agreement matrices per dimension.

**Confidence interval**
: A bootstrap interval around a reported mean, resampling at the question level to show uncertainty from the evaluation set.

**Degraded stage**
: A retrieval stage that timed out or errored while the rest of the request continued. Empty, skipped, and disabled stages have different meanings.

**Evaluation seed question**
: A version-controlled question with reference documents or evidence phrases, and optionally an expert answer, used to measure the target corpus.

**License class**
: One of the five operational redistribution categories attached to every document: `public`, `open_commercial`, `open_noncommercial`, `restricted`, or `unknown`.

**Stage trace**
: Content-free operational metadata for one retrieval stage: status, duration, and candidate count. It is safe to log because it contains no query or chunk text.

**Version stamp**
: The provider/model/dimension identity stored with an embedding so stale rows can be found and re-indexed after a model change.
