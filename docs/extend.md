---
title: Extend the kit
description: Add a parser, corpus collector, reranker, model provider, or authentication backend at Sci RAG Kit's supported extension boundaries.
---

# Extend the kit

Sci RAG Kit has no plug-in registry. It defines five small boundaries where projects vary. Extend at the narrowest seam that fits, and keep its invariants visible in tests and evaluation.

<div class="srag-meta-strip">
  <div><strong>You'll build</strong>A new parser, collector, reranker, provider, or auth backend</div>
  <div><strong>You'll need</strong>A working checkout and its test suite</div>
  <div><strong>Time</strong>An hour to a day, depending on the seam</div>
  <div><strong>Tested with</strong>v0.4</div>
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
| New document type | Produce the shared parsed block model | `src/sci_rag/ingest/parsers.py` | Parser and chunking tests with a fixture |
| New source system | Produce `CorpusEntry` values | `src/sci_rag/ingest/manifest.py` | Metadata, rights, pagination, and resume tests |
| New post-fusion ranking | Implement `Reranker` | `src/sci_rag/retrieve/rerank.py` | Failure fallback test and before/after ablation |
| New embedding or generation model | Implement `EmbeddingProvider` or `LLMClient` | `src/sci_rag/embed/`, `src/sci_rag/llm/` | Offline contract tests plus version and dimension checks |
| New identity system | Implement `AuthBackend` and wire the app factory | `src/sci_rag/server/auth.py` | Auth, scope, rate, REST, and MCP coverage |

## 1. Add a document parser

`parse_file()` dispatches by suffix and returns one `ParsedDocument`. Structured parsers produce ordered `Block` values (`heading`, `text`, or `table`). The chunker owns normalization, token sizing, overlap, and section breadcrumbs.

Uphold these properties:

- Report which route was used when a fallback changes fidelity.
- Keep tables as one block when possible.
- Do not repeat the document title in every section path.
- Fail with the supported list when the suffix is unknown. Blank text is not acceptable.
- Add a test with a fixture demonstrating block order and metadata.

Add the suffix to `SUPPORTED_SUFFIXES`, add a branch in `parse_file()`, and let the ingester handle deduplication, embedding, and transactions.

## 2. Add a corpus collector

A collector emits `CorpusEntry` records containing a local path plus source metadata:

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

Resolve remote bytes to stable local paths before ingestion. Normalize identifiers, retain provider source references, and rate-limit external APIs. Make resume behavior explicit. When you cannot establish redistribution rights, leave `license_class` as `unknown`.

## 3. Add a reranker

`Reranker` is a structural protocol with one async operation:

```python title="src/sci_rag/retrieve/rerank.py"
class Reranker(Protocol):
    name: str

    async def rerank(
        self, query: str, items: list[RetrievedItem], *, top_k: int
    ) -> list[RetrievedItem]: ...
```

The orchestrator passes a wider fused pool and expects a reordered, truncated list. Any exception must record the failure in the trace and revert to the fused order. Add the adapter selection to the domain tuning model only if users need to configure it.

Do not enable a new reranker by default. Run `sci-rag eval retrieval --ablation` with and without it on your corpus, including latency and confidence intervals.

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

Assign a provider-specific version that changes when stored vectors become incompatible. Assert every returned dimension. Distinguish document and query tasks where the model supports asymmetric embeddings. Normalize vectors if the provider's reduced dimensions require it.

An LLM client implements full generation and streaming. JSON consumers call the shared `generate_json()` helper, which requests deterministic JSON mode and strips a surrounding code fence.

Provider additions need a deliberate selection path in `get_embedder()` or `get_llm()`. This factory keeps supported providers in one place.

### Generation providers that ship with the kit

Three adapters live in `src/sci_rag/llm/`, selected by a `provider:model` spec. A bare model id uses `SCI_RAG_LLM_PROVIDER`; a prefixed one overrides it.

| Provider | Reaches | Credentials | Extra |
|---|---|---|---|
| `google` | Gemini | `SCI_RAG_GOOGLE_API_KEY` or `SCI_RAG_GCP_PROJECT` | built in |
| `anthropic` | Claude, on Vertex or the direct API | `SCI_RAG_GCP_PROJECT` (ADC) or `SCI_RAG_ANTHROPIC_API_KEY` | `anthropic` |
| `openai-compatible` | Vertex partner models (Grok, Llama, Mistral, DeepSeek), OpenAI, self-hosted vLLM/Ollama | `SCI_RAG_GCP_PROJECT` (ADC) or `SCI_RAG_OPENAI_API_KEY` (+ optional `SCI_RAG_OPENAI_BASE_URL`) | `openai` |

On Google Cloud, the third row is the only path to non-Google partner models. Vertex serves them behind an OpenAI-compatible endpoint, so one adapter covers current and future models. Model ids keep their publisher prefix, like `xai/grok-4.1-fast-reasoning`. Sending the bare id is rejected.

!!! warning "Partner models are not served from every region"

    `SCI_RAG_GCP_LOCATION` defaults to `us-central1`, which serves Gemini but not Claude or Grok. Both are reachable from `global`, and Grok is only there. Set `SCI_RAG_GCP_LOCATION=global` when generating with a partner model. Google embeddings work from `global` too, though slower than from a region.

    A model that is not served where you asked fails with a `400` (location issue) or `404` (model not found). `sci-rag doctor --probe` catches these before a pipeline run. The probe names `SCI_RAG_GCP_LOCATION=global` as the repair for a `400`. A `404` also covers a wrong model id or an offering this project never enabled.

    Which models a project can reach depends on its Model Garden settings. Treat the ids above as examples to check with `doctor`, not a guaranteed menu.

!!! note "Partner model ids are dated examples"

    Partner models come and go on a schedule this project does not control. Every id here and in `.env.example` last answered both ordinary generation and strict JSON calls on **2026-08-30**, from `global`. Google publishes each model's lifecycle on [Vertex AI partner-models](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/partner-models).

    Verify your models before using them:

    ```console title="Terminal"
    $ make providers-check
    ```

    It calls each model at its documented location and fails when one no longer works. It needs `SCI_RAG_GCP_PROJECT` and application-default credentials. A model absent from your Model Garden also fails it.

### What a new adapter has to normalize

`LLMClient` presents one signature to every call site. An adapter absorbs the differences between providers:

| `generate()` argument | google | anthropic | openai-compatible |
|---|---|---|---|
| `system` | `system_instruction` | `system=` | leading `system` message |
| `temperature` | forwarded | **dropped** | forwarded |
| `max_tokens` | `max_output_tokens` | `max_tokens` (required) | `max_tokens` |
| `json_mode` | `response_mime_type` + `thinking_budget=0` | `output_config={"effort": "low"}` | `response_format` |

Two mappings are tricky:

- **Current Claude models removed the sampling parameters.** Forwarding `temperature` returns a 400, so the Anthropic adapter drops it. Low temperature intent maps to `effort` instead.
- **Lowering effort is not disabling thinking.** Disabling thinking on current Claude models can leak reasoning tags into visible text, corrupting the parsed JSON.
- **Not every Claude model accepts the effort knob.** `claude-sonnet-5` takes it; `claude-haiku-4-5` rejects it. The adapter probes once per client and remembers the result.

Where a provider may reject a knob, adapters retry once without it. Retry policy is shared: `retry_async()` in `llm/client.py` manages backoff. SDK clients are constructed with `max_retries=0` to prevent compounding retries.

### Embeddings are Google-only on purpose

`SCI_RAG_EMBEDDING_PROVIDER` accepts `google` or `local-hash`. There is no third option by design. Anthropic ships no embedding API. On Vertex, the only managed text embeddings are Google's. Every alternative means deploying and paying for your own Model Garden endpoint.

An embedder is not runtime-swappable. A migration bakes `SCI_RAG_EMBEDDING_DIM` into the pgvector column (see [ADR 0002](adr/0002-embeddings-1536-hnsw.md)). Each chunk stores the `version` that produced it. Changing embedders means a migration, full re-embedding, and index rebuild.

`sci-rag embed reindex` plans this work. It reports which rows a version change affects and writes nothing by default. It fails when the dimension you configured does not match the live column. `--apply` is the separate step that re-embeds. Point `SCI_RAG_EMBEDDING_MODEL` at a different Google embedding model freely. Treat anything beyond that as a data migration, not configuration.

## 5. Add an authentication backend

`AuthBackend` has two synchronous operations: authenticate a bearer token into an `AuthContext`, and enforce its rate limit. The shipped factory selects open local mode or static JSON keys from `SCI_RAG_API_KEYS`.

To add OAuth or institutional identity:

1. Map external identity and claims to the existing scope vocabulary.
2. Implement `authenticate()` and `check_rate()`.
3. Wire the backend into the application factory to guard REST and `/mcp`.
4. Keep `application/problem+json` error codes stable.
5. Test REST and MCP access together.

The `create_app()` builds the shipped backend from settings. Keep any factory change explicit. Never import arbitrary authentication code from configuration.

## The invariants around every seam

- **Rights scope precedes ranking.** Apply all document conditions before the candidate limit.
- **Degradation is visible.** Optional components may fail without killing a request, but the trace must name what failed.
- **Stored model output is validated.** Drop or reject unknown ontology values and malformed JSON.
- **REST and MCP share behavior.** Add domain logic to `RagService` before exposing it through either.
- **Tests run offline by default.** Mark credentialed coverage with the `cloud` tag.
- **Retrieval changes come with evidence.** Include ablation results in your pull request.

See [Architecture](architecture.md#extension-points-in-order-of-likely-need) for ownership, [Contributing](contributing.md) for the change bar, and [Evaluate your pipeline](evaluation.md) for the measurement workflow.

<div class="srag-checkpoint" markdown>
**Checkpoint: the seam holds**

`make check` is green, the new code is exercised by an offline test, and if ranking changed there are two ablation tables from the same corpus fingerprint. If any of those three is missing, the change is not done.
</div>

## Next steps

- Produce the before-and-after your change needs: [Evaluate your pipeline](evaluation.md)
- Check the ownership map before widening a seam: [Architecture](architecture.md)
- Read the bar a contribution has to clear: [Contributing](contributing.md)
