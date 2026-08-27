# The sci-rag methodology

This document is the specification the kit is built against. It describes
every design decision that matters, in plain language, so you can judge
whether the approach fits your field, explain it in a paper, or
re-implement it in another stack. The code follows this document, not the
other way around.

In one sentence: hybrid retrieval over a single Postgres database, a
knowledge graph built from a user-defined ontology, fail-closed license
scoping, and an evaluation harness designed to be hard to game.

## 1 Why this shape

Scientific question-answering has three properties that break naive RAG:

1. **The evidence is numeric and tabular.** "What yield should I expect?"
   is answered by a table row, not a vibe. Chunking that shreds tables, or
   retrieval that cannot find the number's context, produces confident
   nonsense.
2. **Questions and documents use different words.** A user asks "how much
   straw does the county produce"; the document says "141,000 harvested
   acres at a 1.1 straw-to-grain ratio". Pure keyword search misses it;
   pure embedding search blurs it.
3. **Corpora mix redistribution rights.** A lab's document pile mixes public
   reports, CC-BY papers, and paywalled PDFs it may hold but not
   redistribute. A RAG that quotes retrieved text IS redistribution, so
   rights have to be a first-class, fail-closed property of retrieval.

Every choice below traces back to one of those three.

## 2 One database

Text, chunks, embeddings, full-text indexes, the knowledge graph, and
licensing metadata all live in a single PostgreSQL database with the
pgvector extension. There is no separate vector store and no graph
database.

This is a deliberate trade. A dedicated graph database is faster at deep
traversals, but this methodology never traverses deeper than two hops
(section 6.3), and one database means one backup, one migration story,
one access-control surface, and transactional consistency between a chunk
and its graph entries. Measure before adding infrastructure: the seams
are there if a corpus ever outgrows this (millions of chunks), but do not
pay the operational cost on day one.

## 3 Ingestion

Every document flows through the same sequence:

```
parse -> chunk -> classify license -> deduplicate -> embed -> store (one transaction)
```

* **Parse.** PDFs go through a structure-preserving parser (Docling when
  installed, pypdf as the fallback), Markdown is parsed directly, plain
  text passes through. All routes produce the same block model: headings,
  tables, and prose.
* **License.** Each document carries a redistribution class declared in
  the corpus manifest: `public`, `open_commercial`, `open_noncommercial`,
  `restricted`, or `unknown`. Nobody said otherwise means `unknown`, and
  `unknown` is treated as unsafe (section 7).
* **Deduplicate.** Content identity is a SHA-256 over the normalized
  chunked text, enforced by a unique constraint. Re-ingesting a file, or
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
  index instead of a full scan. Truncated embeddings are re-normalized to
  unit length before storage (truncation breaks unit norm, and cosine
  ranking assumes it).
* The embedder asserts the returned dimension on every call. A
  model/configuration mismatch fails loudly at the source instead of
  surfacing later as an opaque database error.
* Queries and documents are embedded with their respective task hints
  (asymmetric retrieval), and interactive query embeddings are cached
  briefly in process memory under hashed keys (raw query text is never a
  cache key).

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

At ingestion time, an LLM extracts entities and typed relationships from
each chunk, constrained to a **domain ontology you declare** (entity
types and relation types with one-line descriptions, in a YAML file).
Unknown types and dangling endpoints are dropped, never guessed. Entities
are canonical by name, accumulate evidence pointers (the chunks they were
extracted from), and retain surface-form aliases actually present in the
source. Relationships keep the quoted phrase that stated them and a
calibrated confidence score: 1.0 for direct statements, 0.7 for strong
implications, and 0.4 for inferences across sentences. Re-extraction merges
aliases and preserves the highest confidence observed for a repeated typed
edge from the same evidence surface. Edges with different document or chunk
provenance remain separate so retrieval scope cannot erase otherwise eligible
relationship evidence.

Extraction can still fragment one concept across several names. Run
`sci-rag graph resolve-entities --dry-run` to inspect a conservative
three-tier resolution pass: normalized name and alias overlap first,
high-similarity same-type names second, and one batched LLM decision for
the ambiguous band. Nothing is written until `--apply`. A merge unions
evidence and aliases, repoints relationships, and leaves the old row as a
`canonical_entity_id` tombstone. Every applied merge has a durable row in
`entity_resolution_audit`; `--no-llm` provides a deterministic-only pass.
The doctor reports cheap probable duplicates, and graph GC preserves these
tombstones. Because community summaries materialize entity membership and
relationships, an applied merge clears them; rebuild with
`sci-rag graph communities` after reviewing the resolution receipts.

At query time, a fast LLM call extracts entity names from the question,
matching graph entities are walked up to **two hops** in either
direction, and the chunks those entities point to re-enter the candidate
pool. By default candidates retain the historical hop-distance ordering.
The domain profile may set a minimum relationship confidence, and may rank
by the strongest minimum-edge confidence along each path before using hop
distance as a tie-breaker. Both controls are off by default and must earn
their place through the `confidence_weighted` versus `full_deep` ablation.
This is what makes multi-hop questions work: the connecting entity brings
its evidence with it even when the question's words never appear in that
text.

Alias strings currently do not carry per-surface document provenance, so only
an unrestricted graph walk may expand them. A restricted walk may seed from an
exact active or tombstone name only when that literal surface occurs in one of
the entity's eligible evidence chunks. Resolution tombstones retain their
original evidence pointers for this check. Retrieved chunks are restricted
before ranking, and every traversed relationship must itself carry eligible
document or chunk provenance. Restricted evidence therefore cannot seed,
extend, or contribute a candidate to the walk.

### 6.4 Community summaries

Clusters of tightly connected entities usually map onto real themes in a
corpus. Deterministic label propagation finds the clusters, an LLM writes
a short summary of each, and the summaries are embedded. At query time
the layer runs vector search over the summaries and can return them as
results, which is how "big picture" questions get answered when no single
chunk covers them.

One hard rule: a stored summary aggregates evidence from many documents
before any caller's scope is known, so **this layer disables itself
whenever license, source, or exclusion filters are active**. A scoped
caller must never receive a summary partially built from documents
outside their scope.

### 6.5 HyDE (hypothetical document embeddings)

A fast model writes the short passage a real document WOULD contain if it
answered the question, that passage is embedded as a document, and vector
search runs near it. This bridges question-phrasing and answer-phrasing
(property 2 in section 1). The domain profile can steer the passage style
per query class (an availability question reads like a resource
assessment; a properties question reads like a characterization table).
The generated passage is a search probe only: never shown, never cited.

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

These defaults have held up in production use, but the honest way to tune
them for your corpus is the evaluation harness's ablation mode, which
reports what each layer actually contributes to hit rate before you touch
a weight.

### 6.7 Profiles and degradation

Two profiles set defaults: **interactive** (vector + keyword only, short
per-stage timeouts, query-embedding cache on) for humans waiting on a
spinner, and **deep** (all five layers, generous timeouts) for agents,
batch jobs, and evaluation.

A slow or failing layer degrades rather than breaks: it contributes no
candidates, its status (`timeout`, `error`, `empty`, `skipped`,
`disabled`) is recorded in a per-stage trace, and the caller sees exactly
what ran. Traces are content-free by design (stage, status, duration,
candidate count; never query text or chunk text), so they are always safe
to log.

## 7 Scope precedes ranking

A retrieval scope is the caller's rights: allowed license classes,
allowed sources, excluded documents. Three rules make it trustworthy:

1. **Scope is applied inside every layer's SQL, before ordering and
   limiting.** Filtering after ranking is wrong twice over: an
   out-of-scope row can crowd an eligible row out of a bounded candidate
   pool, and excluded content silently shapes what survives.
2. **An explicitly empty license allowlist means "return nothing".** Fail
   closed, before any embedding call or database query.
3. **`unknown` is never external-safe.** Only `public` and
   `open_commercial` belong on surfaces you do not fully control.

Excluded document IDs use the same mechanism, which is also what makes
evaluation holdouts real (section 9): an excluded document is
unreachable through every layer, including graph traversal, and there is
a regression test proving it.

## 8 Grounded answers

The answer prompt receives numbered sources (the retrieved chunks, each
with title, section path, and citation) and three standing orders: cite
every claim inline by number, prefer the sources' numbers and units over
summary, and when the sources do not contain the answer, say so instead
of improvising. The response carries a structured citation list mapping
each number to its document, and the honesty rule is checked after the
fact by the evaluation judge.

## 9 Evaluation design

* **Ground truth is expert-authored.** A seed question holds the
  question, what a correct answer must say, which documents contain it,
  and a few distinctive evidence phrases. Ten questions an expert vouches
  for beat a hundred vague ones.
* **Retrieval metrics are mechanical and transparent.** A retrieved item
  is relevant if it comes from a reference document or contains an
  evidence phrase (whitespace/case normalized). hit@5, hit@10, and MRR
  are computed per layer-ablation config, so every layer has to earn its
  fusion weight on your corpus.
* **The judge is blind.** Grading happens in two independent passes. The
  grounding pass sees the question, the answer, and exactly the sources
  the assistant retrieved, and scores groundedness, citation accuracy,
  and completeness against those sources only; it never sees the
  reference answer (a judge that does will reward reference-matching
  answers the sources do not support). The correctness pass compares the
  answer to the expert reference in a separate call, without the sources.
  Both run at temperature 0; scores are clamped to a 0-to-2 rubric; a
  malformed judge response is recorded as a failure, never coerced.
* **Numbers carry their context.** Every report is stamped with a corpus
  fingerprint (document/chunk/graph counts, embedding versions, latest
  ingestion time) and the git commit. An eval number without its corpus
  fingerprint is just a rumor.
* **Honesty probes.** Questions tagged `unanswerable` are excluded from
  retrieval metrics and exist to check that the system admits gaps
  instead of inventing answers.

## 10 What this methodology does not do (yet)

Kept out deliberately, with the seams left visible:

* ~~**Cross-encoder reranking** of the fused pool.~~ Filled in v0.2:
  `src/sci_rag/retrieve/rerank.py` ships a `Reranker` protocol with an
  LLM adapter (default, zero new dependencies) and a local
  cross-encoder adapter behind the `rerank` extra. It stays OFF until
  the `with_rerank` vs `no_rerank` ablation justifies it on your
  corpus. GCP users can implement the same protocol against the Vertex
  AI Ranking API (`discoveryengine.googleapis.com` rank endpoint): score
  the pool, return the reordered items, and set `retrieval.reranker`
  in `domain.yaml` to your adapter via a small subclass of the
  retriever or a fork of `build_reranker`.
* **Hierarchical communities** (communities of communities) for very
  large graphs.
* **Automatic license classification** (DOI lookups against registries).
  The manifest declares rights in v1; a classifier can enrich it later,
  but must only ever downgrade toward `restricted`, never upgrade.
* **A learned fusion model.** Weighted RRF is transparent and debuggable;
  do not replace it until an ablation table says so.
