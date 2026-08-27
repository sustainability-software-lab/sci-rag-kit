---
title: Extend the seams
description: Add a parser, corpus collector, reranker, model provider, or authentication backend at Sci-RAG Kit's supported extension boundaries.
---

# Extend the seams

Sci-RAG Kit has no plug-in registry. It has five small boundaries where real projects commonly vary. Extend the narrowest one that matches the change, then keep its surrounding invariants visible in tests and evaluation.

## Choose the seam

| Need | Contract | Primary file | Evidence to add |
|---|---|---|---|
| New document type | Produce the shared parsed block model | `src/sci_rag/ingest/parsers.py` | Parser and chunking tests with a small fixture |
| New source system | Produce `CorpusEntry` values | `src/sci_rag/ingest/manifest.py` | Metadata, rights, pagination, and resume tests |
| New post-fusion ranking | Implement `Reranker` | `src/sci_rag/retrieve/rerank.py` | Failure fallback test and before/after ablation |
| New embedding or generation model | Implement `EmbeddingProvider` or `LLMClient` | `src/sci_rag/embed/`, `src/sci_rag/llm/` | Offline contract tests plus version/dimension checks |
| New identity system | Implement `AuthBackend` and wire the app factory | `src/sci_rag/server/auth.py` | Auth, scope, rate, REST, and MCP coverage |

## 1. Add a document parser

`parse_file()` dispatches by suffix and returns one `ParsedDocument`. Structured parsers should produce ordered `Block` values (`heading`, `text`, or `table`); the chunker then owns normalization, token sizing, overlap, and section breadcrumbs.

Keep these properties:

- A parser reports the route it used when a fallback changes fidelity.
- Tables remain one block when feasible.
- The first document title is not duplicated into every section path.
- Unsupported suffixes fail with the supported list rather than returning blank text.
- A fixture test demonstrates the block order and metadata.

Add the suffix to `SUPPORTED_SUFFIXES`, add a branch in `parse_file()`, and let the existing ingester handle deduplication, embedding, and transactions.

## 2. Add a corpus collector

A collector does not need to know about chunking or storage. It emits `CorpusEntry` records containing a local path plus whatever source metadata it can establish:

```python title="CorpusEntry fields (excerpt from src/sci_rag/ingest/manifest.py)"
path: Path
title: str | None
authors: list[str]
year: int | None
doi: str | None
journal: str | None
url: str | None
license_class: str
source: str
```

Resolve remote bytes to stable local paths before ingestion. Normalize identifiers, retain provider source references, rate-limit external APIs, and make resume behavior explicit. When the collector cannot establish redistribution rights, leave `license_class` as `unknown`.

## 3. Add a reranker

`Reranker` is a structural protocol with one async operation:

```python title="src/sci_rag/retrieve/rerank.py (interface excerpt)"
class Reranker(Protocol):
    name: str

    async def rerank(
        self, query: str, items: list[RetrievedItem], *, top_k: int
    ) -> list[RetrievedItem]: ...
```

The orchestrator passes a wider fused pool and expects a reordered, truncated list. Any exception must leave a visible rerank trace and fall back to the fused order. Add the adapter selection to the validated domain tuning model only if users need to configure it.

Do not enable a new reranker by default from intuition. Run `sci-rag eval retrieval --ablation` with and without it on the target corpus, including latency and confidence intervals.

## 4. Add a model provider

An embedding provider exposes `version`, `dim`, and one batch method:

```python title="src/sci_rag/embed/provider.py (interface excerpt)"
class EmbeddingProvider(ABC):
    version: str
    dim: int

    async def embed(
        self, texts: list[str], *, task: EmbeddingTask
    ) -> list[list[float]]: ...
```

Stamp a provider-specific version that changes when stored vectors become incompatible. Assert every returned dimension, distinguish document and query tasks where the model supports asymmetric embeddings, and normalize vectors if the provider's reduced dimensions require it.

An LLM client implements full generation and streaming. JSON consumers use the shared `generate_json()` helper, which requests deterministic JSON mode and strips a surrounding code fence before parsing.

Provider additions also need a deliberate selection path in `get_embedder()` or `get_llm()`. That small factory is preferable to a general plug-in loader because supported providers remain visible in one file.

## 5. Add an authentication backend

`AuthBackend` has two synchronous operations: authenticate a bearer token into an `AuthContext`, and enforce its rate limit. The shipped factory selects open local mode or static JSON keys from `SCI_RAG_API_KEYS`.

A deployment that adds OAuth or institutional identity should:

1. Map the external identity and claims to the existing scope vocabulary.
2. Implement `authenticate()` and `check_rate()`.
3. Wire the backend into its application factory so the same instance guards REST and the `/mcp` mount.
4. Preserve stable `application/problem+json` error codes.
5. Test REST and MCP access together.

The current `create_app()` constructs the shipped backend from settings; it is not a run-time plug-in registry. Keep any factory change explicit rather than importing arbitrary authentication code from configuration.

## The invariants around every seam

- **Rights scope precedes ranking.** A new retrieval path must apply all document conditions before its candidate limit.
- **Degradation is visible.** An optional component may fail without killing a request, but its trace must say so.
- **Stored model output is validated.** Unknown ontology values and malformed JSON are dropped or rejected, not guessed into shape.
- **REST and MCP share behavior.** Add domain logic to `RagService` or a lower facade before exposing it through either adapter.
- **Tests run offline by default.** Put credentialed smoke coverage behind the `cloud` marker.
- **Retrieval changes bring receipts.** Include ablation results in the pull request.

See [Architecture](architecture.md#extension-points-in-order-of-likely-need) for ownership, [Contributing](contributing.md) for the change bar, and [Evaluation](evaluation.md) for the measurement workflow.
