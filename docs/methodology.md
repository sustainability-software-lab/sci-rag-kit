---
title: Methodology
description: Read the specification behind chunking, graph extraction, fusion, answer generation, and evaluation, with the reasoning for every choice.
---

# Methodology

This document is the kit's specification. It describes every design
decision that matters, in plain language. You should be able to judge
whether the approach fits your field, explain it in a paper, or
re-implement it in another stack. The code follows this document, not the
other way around.

In one sentence: hybrid retrieval over a single Postgres database, a
knowledge graph built from a user-defined ontology, fail-closed license
scoping, and an evaluation harness designed to be hard to game.

## 1 Why this shape

Scientific question-answering has three properties that break naive RAG:

1. **The evidence is numeric and tabular.** The answer to "What yield should I expect?" is a table row with numbers, not a summary. Chunking that shreds tables, or retrieval that cannot find the number's context, produces confident, wrong answers.
2. **Questions and documents use different words.** A user asks "how much straw does the county produce"; the document says "141,000 harvested acres at a 1.1 straw-to-grain ratio". Keyword search alone misses this; embedding search alone blurs the specific numbers.
3. **Corpora mix redistribution rights.** A lab's document pile mixes public reports, CC-BY papers, and paywalled PDFs it may hold but not redistribute. A RAG that quotes retrieved text **is** redistribution, so rights have to be a first-class property of every retrieval layer.

Every choice below traces back to one of those three.

## 2 One database

Text, chunks, embeddings, full-text indexes, the knowledge graph, and licensing metadata all live in a single PostgreSQL database with the pgvector extension. There is no separate vector store and no graph database.

A dedicated graph database is faster at deep traversals. This methodology never traverses deeper than two hops (section 6.3), and one database means one backup, one migration story, one access-control surface, and transactional consistency between a chunk and its graph entries. The seams are visible if a corpus outgrows this architecture (millions of chunks), but do not pay the operational cost before you need it.

## 3 Ingestion

Every document flows through the same sequence:

```
parse -> chunk -> classify license -> deduplicate -> embed -> store (one transaction)
```

* **Parse.** PDFs go through a structure-preserving parser (Docling when
  installed, pypdf as the fallback). Markdown parses directly. HTML goes
  through the standard library's parser, which drops page chrome (`nav`,
  `header`, `footer`, `aside`, scripts and styles) so a shared sidebar does
  not become the most repeated text in the corpus, and renders tables as pipe
  tables so they take the same path a Markdown table does. Plain text passes
  through. All routes produce the same block model: headings, tables, and
  prose.
* **License.** Each document carries a redistribution class declared in
  the corpus manifest: `public`, `open_commercial`, `open_noncommercial`,
  `restricted`, or `unknown`. Nobody said otherwise means `unknown`, and
  the kit treats `unknown` as unsafe (section 7).
* **Deduplicate.** Content identity is a SHA-256 over the normalized
  chunked text, and a unique constraint enforces it. Re-ingesting a file, or
  the same content under a new filename, is a no-op.
* **Store transactionally.** A document and all its chunks commit
  together or not at all; a crash cannot leave half a document behind.

## 4 Structure-aware chunking

A generic recursive text splitter throws away the two most valuable
signals in technical writing: where a statement sits in the section
hierarchy, and whether a table survives intact. The chunker keeps both:

1. Normalize the raw text: form feeds, stray page-number lines,
   end-of-line hyphenation ("ligno-\ncellulosic" becomes
   "lignocellulosic"), null bytes.
2. Segment into paragraphs; drop fragments under 20 characters (almost
   always extraction noise).
3. Detect headings three ways: numbered ("2.1 Feedstock handling"), ALL
   CAPS, and short Title Case lines. Maintain a section path such as
   "2 Methods > 2.1 Feedstock handling".
4. Detect table-like paragraphs (pipe tables, tab columns, aligned space
   grids) and emit each table as its own intact chunk, flagged
   `is_table`.
5. Merge ordinary paragraphs up to a target of **800 tokens**, splitting
   oversized paragraphs on sentence boundaries, and never merging across
   a section boundary.
6. Carry roughly **150 tokens** of trailing overlap into the next prose
   chunk (tables hand over at most their last two rows), and never carry
   overlap across a heading.
7. Prepend the document title and section path to every chunk, so each
   chunk embeds and reads sensibly on its own.

The 800/150 defaults suit dense technical PDFs; both are parameters.

## 5 Embeddings

* One embedding model per corpus, with the model identity stamped on
  every chunk (`embedding_version`). A model upgrade is then a findable
  migration ("re-embed rows whose version is stale"), never a silent
  mixture of incompatible vectors.
* The default dimension is **1536**, requested from the model by
  Matryoshka truncation. This keeps vectors inside pgvector's
  2000-dimension HNSW index limit, so nearest-neighbor search uses a real
  index instead of a full scan. The embedder re-normalizes truncated
  embeddings to unit length before storage, because truncation breaks the
  unit norm that cosine ranking assumes.
* The embedder asserts the returned dimension on every call. A
  model/configuration mismatch fails loudly at the source instead of
  surfacing later as an opaque database error.
* Queries and documents each embed with their own task hint, which is what
  asymmetric retrieval means: the same words are encoded differently
  depending on which side of the search they sit on. Interactive query
  embeddings cache briefly in process memory under hashed keys, and the raw
  query text is never a cache key.

## 6 The five retrieval layers

Five candidate generators run in parallel, each with its own database
session and its own timeout, and their ranked lists fuse once.

### 6.1 Dense vector search

Cosine similarity over chunk embeddings, served by HNSW. The workhorse;
carries the highest fusion weight.

### 6.2 Keyword full-text search

Postgres full-text search over a generated `tsvector` column (GIN
indexed), using `websearch_to_tsquery` so raw user input is always safe.
This layer catches exact terms, identifiers, and chemical names that
embeddings blur.

### 6.3 Knowledge-graph traversal

Four things happen in this layer, at two different times. Extraction and
entity resolution run when documents are ingested. The walk and its scope
rules run on every query that reaches the stage.

#### 6.3.1 Extraction

At ingestion time, an LLM extracts entities and typed relationships from each chunk. A **domain ontology you declare** constrains it: entity types and relation types with one-line descriptions, in a YAML file. The extractor drops unknown types and dangling endpoints rather than guessing. Entities are canonical by name. They accumulate evidence pointers (the chunks they came from) and retain surface-form aliases as they appear in the source.

Relationships keep the quoted phrase that stated them and a confidence score: 1.0 for direct statements, 0.7 for strong implications, and 0.4 for cross-sentence inferences. Re-extraction merges aliases and preserves the highest confidence for a typed edge from the same evidence surface. Edges with different document or chunk provenance stay separate; retrieval scope cannot erase otherwise eligible relationship evidence.

#### 6.3.2 Entity resolution

Extraction can still fragment one concept across several names. Run `sci-rag graph resolve-entities --dry-run` to inspect a three-tier resolution pass: normalized name and alias overlap first, high-similarity same-type names second, and one batched LLM decision for the ambiguous cases. Nothing lands until `--apply`. A merge unions evidence and aliases, repoints relationships, and leaves the old row as a `canonical_entity_id` tombstone (a marked deleted record). Every applied merge has a durable row in `entity_resolution_audit`. Use `--no-llm` for deterministic-only merges. The doctor reports probable duplicates, and graph cleanup preserves these tombstones. Because community summaries materialize entity membership, an applied merge clears them. Rebuild with `sci-rag graph communities` after reviewing the resolution results.

#### 6.3.3 The two-hop walk

At query time, a fast LLM call extracts entity names from the question. The walk follows matching graph entities up to **two hops** in either direction, and the chunks those entities point to re-enter the candidate pool. By default, candidates retain the hop-distance ordering.

The domain profile can set a minimum relationship confidence and rank by the strongest minimum-edge confidence along each path before using hop distance as a tie-breaker. Both are off by default; they must earn their place through the `confidence_weighted` versus `full_deep` ablation (a test that measures their contribution). The graph stage can also expand the represented documents by one resolved citation hop in either direction; this is off by default. It uses only `document_citations` rows whose target resolves to a corpus document and applies the request scope to the neighboring document before chunk ranking. The `with_citations` ablation measures its effect. Unresolved DOI pointers remain visible provenance and never enter retrieval.

This architecture makes multi-hop questions work. The connecting entity brings its evidence with it even when the question's words do not appear in that text.

#### 6.3.4 Scope inside the walk

Alias strings currently do not carry per-surface document provenance; only an unrestricted graph walk may expand them. A restricted walk may seed from an exact active or tombstone name only when that literal surface occurs in one of the entity's eligible evidence chunks. Resolution tombstones retain their original evidence pointers for this check. The walk restricts retrieved chunks before ranking. Every traversed relationship must carry eligible document or chunk provenance. Restricted evidence therefore cannot seed, extend, or contribute a candidate to the walk.

### 6.4 Community summaries

Clusters of tightly connected entities usually map to real themes in a corpus. Deterministic label propagation finds the clusters. An LLM writes a short summary of each, and the embedder embeds those summaries. At query time, the layer runs vector search over the summaries and can return them as results. This is how the layer answers "big picture" questions when no single chunk covers them.

One hard rule: a stored summary aggregates evidence from many documents before any caller's scope is known. **This layer disables itself whenever license, source, or exclusion filters are active.** A scoped caller must never receive a summary built from documents outside their scope.

### 6.5 HyDE (hypothetical document embeddings)

A fast model writes a short passage that a real document would contain if it answered the question. That passage embeds as if it were a document, and vector search runs near it. This bridges question-phrasing and answer-phrasing (property 2 in section 1). The domain profile can steer the passage style per query class: an availability question reads like a resource assessment; a properties question reads like a characterization table. The generated passage is a search probe only: never shown, never cited.

### 6.6 Fusion

Weighted reciprocal rank fusion:

```
score(c) = sum over layers of  weight_layer / (k + rank_of_c_in_layer)
```

with rank starting at 1 and k = 60. Native scores (cosine distance,
ts_rank, hop counts) are incomparable across layers; ranks are not. A
candidate several layers agree on beats a candidate one layer loved.

| Layer | Default weight |
|-------|---------------:|
| vector | 1.5 |
| keyword | 1.0 |
| graph | 0.8 |
| community | 0.6 |
| HyDE | 1.2 |

These defaults have held up in production use. To tune them for your own
corpus, use the evaluation harness's ablation mode: it reports what each
layer actually contributes to hit rate before you touch a weight.

### 6.7 Profiles and degradation

Two profiles set defaults: **interactive** (vector + keyword only, short
per-stage timeouts, query-embedding cache on) for humans waiting on a
spinner, and **deep** (all five layers, generous timeouts) for agents,
batch jobs, and evaluation.

A slow or failing layer degrades rather than breaks. It contributes no
candidates, a per-stage trace records its status (`timeout`, `error`,
`empty`, `skipped`, `disabled`), and the caller sees exactly what ran.
Traces are content-free by design (stage, status, duration,
candidate count; never query text or chunk text), so they are always safe
to log.

## 7 Scope precedes ranking

A retrieval scope is the caller's rights: allowed license classes,
allowed sources, excluded documents. Three rules make it trustworthy:

1. **Every layer applies scope inside its own SQL, before ordering and
   limiting.** Filtering after ranking is wrong twice over: an
   out-of-scope row can crowd an eligible row out of a bounded candidate
   pool, and excluded content silently shapes what survives.
2. **An explicitly empty license allowlist means "return nothing".** Fail
   closed, before any embedding call or database query.
3. **`unknown` is never external-safe.** Only `public` and
   `open_commercial` belong on surfaces you do not fully control.

Excluded document IDs use the same mechanism, which is also what makes
evaluation holdouts real (section 9). An excluded document is unreachable
through every layer, including graph traversal, and a regression test
proves it.

Every document carries one of five license classes. Missing or unrecognized
values normalize to `unknown`.

| Class | Meaning | Typical examples |
|---|---|---|
| `public` | Public domain or equivalent; safe to redistribute | CC0, many US federal works |
| `open_commercial` | An open license that permits commercial reuse under its conditions | CC BY, CC BY-SA |
| `open_noncommercial` | An open license that restricts commercial reuse | CC BY-NC variants |
| `restricted` | You may hold the source but not redistribute its text | Paywalled version of record, proprietary report |
| `unknown` | Nobody has established the rights | The default for incomplete metadata |

The taxonomy is operational, not legal advice. Record the actual license and any attribution requirement separately. To see what a corpus holds, by document and by chunk, run:

```bash
sci-rag corpus license-report            # the table
sci-rag corpus license-report --strict   # exit 1 if anything is still `unknown`
```

Retraction is a fourth scope dimension with a default. Crossref enrichment records whether a document has been retracted. The `exclude_retracted` flag drops those documents inside every layer's SQL, like any other scope condition. Answering turns it on by default; raw retrieval does not, because inspecting what a retracted paper claimed is legitimate and the caller has asked for candidates rather than for an answer. A retraction discovered after ingestion changes the next answer without re-ingesting. The `doctor` command reports the count, so a corpus cannot quietly acquire retracted sources.

## 8 Grounded answers

The answer prompt receives numbered sources: the retrieved chunks, each
with title, section path, and citation. It also carries three standing
orders. Cite every claim inline by number. Prefer the sources' numbers and
units over summary. And when the sources do not contain the answer, say so
instead of improvising.

The response carries a structured citation list mapping each number to its
document, and the evaluation judge checks that honesty rule after the
fact. A citation proves which stored passage the answer referenced: its
title, formatted citation, document and chunk identifiers, section path,
license class, source bucket, and the retrieval layers that found it. It
does not prove that the source's method is sound or that the model read it
correctly; that judgment stays with the reader.

Between retrieval and prompt assembly, sources may be compressed: question-aware summarization of each chunk, dropping any whose relevance falls below a floor. This shortens the prompt without changing which documents are cited. Compression is off in the model default and on for the shipped demo domain. Compression only earns a default where a paired judged-answer evaluation holds every quality dimension while measured prompt tokens fall.

The relevance floor decides whether a source is summarized or discarded. A v0.3 floor sweep tested both. At 0.15 and above, groundedness and citation accuracy fall below ceiling: the answer loses evidence it needed. At 0.0, where every source is summarized and none dropped, three paired runs held every dimension while median prompt tokens fell by a quarter. The demo ships at 0.0, and the model default floor matches it. The numbers are on the [benchmarks page](benchmarks.md). To use compression on your own corpus, run that gate there; do not inherit the demo's result. Raising the floor requires running the gate again.

## 9 Evaluation design

* **Ground truth is expert-authored.** A seed question holds the question, what a correct answer must say, which documents contain it, and a few distinctive evidence phrases. Ten questions an expert vouches for outweigh a hundred vague ones.
* **Retrieval metrics are mechanical and transparent.** A retrieved item is relevant if it comes from a reference document or contains an evidence phrase (whitespace and case normalized). The harness computes hit@5, hit@10, and MRR per layer-ablation config, so every layer must earn its fusion weight on your corpus.
* **The judge is blind.** Grading happens in two independent passes. The grounding pass sees the question, the answer, and exactly the sources the assistant retrieved. It scores groundedness, citation accuracy, and completeness against those sources only, and it never sees the reference answer. A judge that does see the reference will reward reference-matching answers the sources do not support. The correctness pass compares the answer to the expert reference in a separate call, without the sources. Both run at temperature 0. Scores clamp to a 0-to-2 rubric, and a malformed judge response is a failure, never a coerced score.
* **Numbers carry their context.** Every report carries a corpus fingerprint (document, chunk, and graph counts, embedding versions, latest ingestion time) and the git commit. A fingerprint documents what corpus state produced that result.
* **Honesty probes.** Questions tagged `unanswerable` sit outside the retrieval metrics. They check that the system admits gaps instead of inventing answers.

## 10 What this methodology does not do (yet)

Kept out deliberately, with the seams left visible:

* ~~**Cross-encoder reranking** of the fused pool.~~ Filled in v0.2:
  `src/sci_rag/retrieve/rerank.py` ships a `Reranker` protocol with an
  LLM adapter (default, zero new dependencies) and a local
  cross-encoder adapter behind the `rerank` extra. It stays **off** until
  the `with_rerank` versus `no_rerank` ablation justifies it on your
  corpus. GCP users can implement the same protocol against the Vertex
  AI Ranking API, meaning the `discoveryengine.googleapis.com` rank
  endpoint. Score the pool, return the reordered items, and point
  `retrieval.reranker` in `domain.yaml` at your adapter, through a small
  subclass of the retriever or a fork of `build_reranker`.
* **Hierarchical communities** (communities of communities) for very
  large graphs.
* **Automatic license classification** (DOI lookups against registries).
  The manifest declares rights in v1; a classifier can enrich it later,
  but must only ever downgrade toward `restricted`, never upgrade.
* **A learned fusion model.** Weighted RRF is transparent and debuggable;
  do not replace it until an ablation table says so.
