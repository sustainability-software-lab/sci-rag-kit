---
title: Extend the seams
description: Add a parser, corpus collector, reranker, model provider, or authentication backend at Sci RAG Kit's supported extension boundaries.
---

# Extend the seams

Sci RAG Kit has no plug-in registry. It has five small boundaries where real projects vary, and by the end of this page you will know which one your change belongs behind and what evidence it owes. Extend the narrowest seam that fits, then keep its surrounding invariants visible in tests and evaluation.

<div class="srag-meta-strip">
  <div><strong>You'll build</strong>A new parser, collector, reranker, provider, or auth backend</div>
  <div><strong>You'll need</strong>A working checkout and its test suite</div>
  <div><strong>Time</strong>An hour to a day, depending on the seam</div>
  <div><strong>Tested with</strong>v0.3</div>
</div>

## Before you start

| Requirement | Why | Check |
|---|---|---|
| `make check` green on an unmodified checkout | So a failure afterwards is yours | `make check` |
| A read of [Architecture](architecture.md) | The seams only make sense against the ownership map | |
| An evaluation baseline, for anything touching ranking | A retrieval change without a before is not measurable | `uv run sci-rag eval retrieval --ablation` |

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

```python title="src/sci_rag/ingest/manifest.py"
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

```python title="src/sci_rag/retrieve/rerank.py"
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

```python title="src/sci_rag/embed/provider.py"
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

### Generation providers that ship with the kit

Three adapters live beside each other in `src/sci_rag/llm/`, selected by a `provider:model` spec. A bare model id belongs to `SCI_RAG_LLM_PROVIDER`; a prefixed one overrides it for that role.

| Provider | Reaches | Credentials | Extra |
|---|---|---|---|
| `google` | Gemini | `SCI_RAG_GOOGLE_API_KEY` or `SCI_RAG_GCP_PROJECT` | built in |
| `anthropic` | Claude, on Vertex or the direct API | `SCI_RAG_GCP_PROJECT` (ADC) or `SCI_RAG_ANTHROPIC_API_KEY` | `anthropic` |
| `openai-compatible` | Vertex partner models (Grok, Llama, Mistral, DeepSeek), OpenAI, self-hosted vLLM/Ollama | `SCI_RAG_GCP_PROJECT` (ADC) or `SCI_RAG_OPENAI_API_KEY` (+ optional `SCI_RAG_OPENAI_BASE_URL`) | `openai` |

On Google Cloud the third row is the only route to the non-Google partner models: Vertex serves them behind an OpenAI-compatible endpoint rather than a native API, so one adapter covers every current and future partner model. Model ids there keep their publisher prefix, as in `xai/grok-4.1-fast-reasoning`; sending the bare id is rejected as a malformed publisher model.

!!! warning "Partner models are not served from every region"

    `SCI_RAG_GCP_LOCATION` defaults to `us-central1`, which serves Gemini but **not** Claude or Grok. Both are reachable from `global`, and Grok is only offered there. Set `SCI_RAG_GCP_LOCATION=global` when generating with a partner model; Google embeddings work from `global` too, though noticeably slower than from a region. A model that is not served where you asked fails with a clear `400 ... is not servable in region` or `404 ... not found`, so `sci-rag doctor --probe` will catch it before a pipeline run does.

    Which models a project can reach also depends on what is enabled in its Model Garden, so treat the ids above as examples to check with `doctor`, not a guaranteed menu.

### What a new adapter has to normalize

`LLMClient` presents one signature to every call site, so an adapter absorbs the differences between providers rather than exposing them:

| `generate()` argument | google | anthropic | openai-compatible |
|---|---|---|---|
| `system` | `system_instruction` | `system=` | leading `system` message |
| `temperature` | forwarded | **dropped** | forwarded |
| `max_tokens` | `max_output_tokens` | `max_tokens` (required) | `max_tokens` |
| `json_mode` | `response_mime_type` + `thinking_budget=0` | `output_config={"effort": "low"}` | `response_format` |

Two of those cells are easy to get wrong:

- **Current Claude models removed the sampling parameters.** Forwarding `temperature` returns a 400, so the Anthropic adapter drops it. The intent behind a low temperature maps onto `effort` instead.
- **Lowering effort is not the same as disabling thinking.** Disabling it on current Claude models can leak reasoning tags or write a tool call into visible text, which would corrupt the JSON the extraction and judge call sites parse.
- **Not every Claude model accepts the effort knob.** `claude-sonnet-5` takes it; `claude-haiku-4-5` rejects it with `400 output_config.effort: Extra inputs are not permitted`. The adapter probes once per client and remembers the result, because re-learning it per call would double the request count across a graph-extraction run.

Where a provider may reject a knob, the adapters retry once without it rather than failing the call. Retry policy itself is shared: `retry_async()` in `llm/client.py` owns the backoff, and the SDK clients are constructed with `max_retries=0` so their own retries do not compound with it.

### Embeddings are Google-only on purpose

`SCI_RAG_EMBEDDING_PROVIDER` accepts `google` or `local-hash`, and there is no third option by design. Anthropic ships no embedding API, and on Vertex the only *managed* text embeddings are Google's; every alternative means deploying and paying for your own Model Garden endpoint.

More to the point, an embedder is not a runtime-swappable choice here. A migration bakes `SCI_RAG_EMBEDDING_DIM` into the pgvector column (see [ADR 0002](adr/0002-embeddings-1536-hnsw.md)), and each chunk stores the `version` that produced it. Changing embedder means a migration, a full re-embed, and an index rebuild. `sci-rag embed plan` exists to scope exactly that work. Point `SCI_RAG_EMBEDDING_MODEL` at a different Google embedding model freely; treat anything beyond that as a data migration, not a configuration change.

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

<div class="srag-checkpoint" markdown>
**Checkpoint: the seam holds**

`make check` is green, your new code is exercised by an offline test, and if
you touched ranking you have two ablation tables from the same corpus
fingerprint. If any of those three is missing, the change is not done.
</div>

## Next steps

- Produce the before-and-after your change needs: [Evaluate your pipeline](evaluation.md)
- Check the ownership map before widening a seam: [Architecture](architecture.md)
- Read the bar a contribution has to clear: [Contributing](contributing.md)
