---
title: REST, MCP, and Python API
description: Look up authentication scopes, endpoint shapes, streaming events, agent tools, error codes, and importable entry points.
---

# REST, MCP, and Python API

One server, two front doors, one service behind both. Start it with
`sci-rag serve`; interactive OpenAPI docs live at `/docs`.

## Authentication

Send `Authorization: Bearer <key>`, or `X-API-Key: <key>` where something
upstream has already claimed the first one. Cloud Run is the case that
matters: its frontend inspects `Authorization: Bearer` and rejects anything
that is not one of its own identity tokens, before your container sees the
request, so on a deployed service the second header is the one that works.
`Authorization` wins when both are sent.

Keys are configured by the operator as a JSON map in `SCI_RAG_API_KEYS`:

```json
{"team-key":  {"scopes": ["retrieval:query", "retrieval:answer", "corpus:read"],
               "rate_limit_per_minute": 120},
 "agent-key": {"scopes": ["retrieval:query", "retrieval:answer", "byo_llm"]}}
```

| Scope | Grants |
|-------|--------|
| `retrieval:query` | `POST /v1/query`, and the MCP mount |
| `retrieval:answer` | `POST /v1/answer` (spends LLM tokens) |
| `corpus:read` | document catalog and `/v1/status` |
| `byo_llm` | may supply `llm_api_key` per request |

With no keys configured the server runs **open** and warns loudly at
startup; that is for localhost development only. `GET /health` and
`GET /v1/corpus-manifest` never require auth.

## Errors

Every error is RFC 9457 `application/problem+json` with a stable `code`
and the request id:

```json
{"type": ".../docs/api.md#invalid_key", "title": "Unknown API key",
 "status": 401, "code": "invalid_key", "detail": "", "request_id": "9f2c..."}
```

The same id comes back in the `X-Request-ID` response header on every
response, error or not. Send your own in the request header to have it
echoed, and quote it when you ask an operator to find the call in the
logs. A `500` never carries the underlying exception message, the query,
or any chunk text: it names the exception type and points at the logs.

Codes you can branch on:

| Code | Status | Meaning |
|------|-------:|---------|
| <a id="missing_key"></a>`missing_key` | 401 | No bearer token; `WWW-Authenticate: Bearer` is set |
| <a id="invalid_key"></a>`invalid_key` | 401 | Token not recognized |
| <a id="insufficient_scope"></a>`insufficient_scope` | 403 | Key lacks the required scope |
| <a id="rate_limited"></a>`rate_limited` | 429 | Over the per-key limit; honor `Retry-After` |
| <a id="invalid_request"></a>`invalid_request` | 422 | Body failed validation |
| <a id="document_not_found"></a>`document_not_found` | 404 | Unknown document id |
| <a id="llm_unavailable"></a>`llm_unavailable` | 503 | No LLM credentials configured server-side |
| <a id="generation_failed"></a>`generation_failed` | 502 | The model call failed |
| <a id="http_error"></a>`http_error` / <a id="internal_error"></a>`internal_error` | varies | Everything else, with the request id for the logs |

## REST endpoints

### POST /v1/query

Retrieval only: ranked evidence with full transparency, no generation.

```bash
curl -s -X POST localhost:8000/v1/query \
  -H 'Authorization: Bearer team-key' -H 'Content-Type: application/json' \
  -d '{"query": "biogas yield of pretreated rice straw",
       "top_k": 5, "profile": "deep",
       "license_classes": ["public", "open_commercial"]}'
```

Request fields:

* `query`, required.
* `top_k`, 1 to 50, default 8.
* `profile`: `interactive` (the default), `deep`, or `auto`.
* Per-layer overrides: `include_graph`, `include_community`,
  `include_hyde`, `include_rerank`.
* `license_classes` and `sources` allowlists. Omit them for all; an empty
  license list returns nothing by design.
* The metadata filters below.
* `include_content: false` for lean responses.

**Metadata filters.** `year_min`, `year_max`, `authors`, `journals`, and
`exclude_dois` narrow by publication metadata:

```bash
curl -s -X POST localhost:8000/v1/query \
  -H 'Authorization: Bearer team-key' -H 'Content-Type: application/json' \
  -d '{"query": "pretreatment of rice straw", "top_k": 5,
       "year_min": 2020, "journals": ["Biomass and Bioenergy"],
       "exclude_dois": ["10.1016/j.biombioe.2019.00000"]}'
```

They are enforced inside every layer's SQL, before ranking, exactly like
the license scope: an out-of-range document can never crowd an eligible
one out of a bounded candidate pool. `authors` and `journals` match
whole stored strings, not substrings. One consequence to expect: **any**
filter disables the community layer. A stored community summary aggregates
evidence across documents before your scope is known, so nothing can
filter it after the fact. The `community` trace reads `skipped` when that
happens. `journal` can come directly from your manifest or be
refreshed from explicit Crossref metadata with `sci-rag corpus enrich`.

The response carries three things: `items`, `traces`, and
`degraded_stages`. Each item has a title, section path, citation, license
class, fused score, and a `layers` field naming the layers that found it.
Each trace has a per-stage status and timing. If something timed out, you
will know exactly what.

### POST /v1/answer

A grounded, cited answer. Two modes in one endpoint:

**Streaming (default).** `"stream": true` returns Server-Sent Events:

```
event: retrieval_started   data: {"profile": "deep"}
event: retrieval_done      data: {"item_count": 8, "degraded_stages": [], "traces": [...]}
event: compression_done    data: {"enabled": true, "prompt_tokens_before": 1408, "prompt_tokens_after": 462, ...}
event: generation_started  data: {"model": "gemini-3.6-flash"}
event: delta               data: {"text": "Given its ash content, ..."}   (repeats)
event: citations           data: {"citations": [{"index": 1, "title": "...", "cited": true, ...}]}
event: done                data: {"finish_reason": "stop"}
```

`finish_reason` is `stop` for a generated answer, `no_sources` when the
allowed scope holds no matching material, `no_relevant_sources` when what was
retrieved does not support an answer, and `retrieval_timeout` when the stages
that could have supplied evidence ran out of budget. The last one also carries
`timed_out_stages`, and it is deliberately distinct from `no_sources`: a
corpus nobody could reach is not an empty corpus.

An `error` event (`code`, `message`) replaces the tail on failure.

**JSON.** `"stream": false` returns one body: `answer`, `model`,
`citations` (with a `cited` flag per source), `traces`,
`degraded_stages`, measured `prompt_tokens_before` and
`prompt_tokens_after`, plus compression failure and dropped-source counts.

Set `include_compression` to `true` or `false` to override the domain's
`compression.enabled` setting. Compression relevance-scores ordinary chunks
and summarizes them before prompt assembly. The shipped demo enables it after
the paired judged-answer gate documented in [Evaluate your pipeline](evaluation.md); a new
domain should run the same gate before enabling its default. Failed, malformed,
empty, duplicate, or over-budget model output falls back to the complete chunk
and increments `compression_failure_count`; it never silently removes the
evidence. Citations always retain the original document and chunk identity.

Known retracted documents are excluded from answers by default. The flag
comes from explicit Crossref metadata written by `sci-rag corpus enrich`;
missing enrichment is not guessed to mean retracted. Raw `/v1/query`
retrieval keeps its previous behavior so evaluation and inspection remain
deliberate. The CLI has `sci-rag answer --include-retracted` for the rare,
explicit case where an operator needs retracted evidence in an answer.

**Bring your own key.** A request may include `llm_api_key` (an AI
Studio key) if its API key holds the `byo_llm` scope; the operator can
also bind an LLM key to an API key server-side. Either way the
credential is used for that call only and never stored or logged.

### GET /v1/documents and GET /v1/documents/{id}

The corpus catalog (scope `corpus:read`): paginated summaries with
title, source, license class, authors, and counts; filters `search`
(title substring), `source`, `license_class`. The detail view adds the
formatted citation, source ref, and chunk previews.

### GET /v1/status, GET /health, GET /v1/corpus-manifest

`status` (scope `corpus:read`): counts of everything plus breakdowns by
license, source, and embedding version. `health` (no auth): liveness
plus a database check, Cloud Run friendly. `corpus-manifest` (no auth,
deliberately): the machine-readable descriptor of this knowledge base:
domain, counts, embedding model and dimension, retrieval layers and
fusion weights, endpoint URLs, feature flags. A router in front of
several sci-rag deployments (the "switchboard" pattern) reads this to
decide which knowledge base fits a query.

## MCP

Same capabilities as tools for agents. Two transports:

* **stdio** (local agents): `sci-rag mcp`, or one-line registration:
  `claude mcp add my-corpus -- uv run --directory /path/to/repo sci-rag mcp`
* **Streamable HTTP** (remote agents): `POST /mcp/` on the running
  server, guarded by the same bearer keys (scope `retrieval:query`).

The eight tools:

| Tool | Use it to |
|------|-----------|
| `search_corpus(query, top_k, deep, license_classes, year_min, year_max, journals)` | get ranked evidence chunks to reason over yourself |
| `answer_question(query, top_k, license_classes)` | get a grounded answer with numbered citations |
| `get_document(document_id)` | inspect a cited source: metadata, license, chunk previews |
| `get_citations(document_id)` | follow its references and the corpus documents that cite it |
| `search_entities(name_contains, entity_type, limit)` | find knowledge-graph entities by name |
| `get_entity_relationships(entity_name)` | see every stated relationship of an entity, with evidence quotes |
| `list_sources()` | learn the corpus's source buckets and license mix |
| `corpus_stats()` | size and shape; a fast "is this corpus worth querying" check |

Plus two resources: `corpus://manifest` (same payload as the REST
manifest) and `corpus://methodology` (how retrieval works here, one
page). Tool descriptions are written for the agent reading them; if you
add tools, hold that bar.

## Generated clients

The running server publishes its schema at `/openapi.json`, so a typed client
in any language is one generator call away. Two that work with the shipped
schema:

```console title="Terminal"
$ uvx openapi-python-client generate --url http://127.0.0.1:8000/openapi.json
$ npx openapi-typescript http://127.0.0.1:8000/openapi.json -o sci-rag.d.ts
```

The first writes an installable Python package, the second a TypeScript
type file. Pass the key as `Authorization: Bearer <key>` (or `X-API-Key`
behind Cloud Run) exactly as with `curl`; the generated clients add nothing
to the authentication contract above.

## Python API

The CLI and server are thin wrappers over importable pieces, so the same
capabilities work in notebooks and your own applications. The package
ships type information (`py.typed`).

```python
from sci_rag import Retriever, AnswerEngine, RetrievalScope

retriever = Retriever()  # settings from the environment, domain from domain/
result = await retriever.retrieve(
    "rice straw availability",
    profile="deep",
    limit=5,
    scope=RetrievalScope(
        license_classes=("public", "open_commercial"),
        year_min=2020,
        journals=("Biomass and Bioenergy",),
    ),
)
for item in result.items:
    print(item.title, item.layers, item.score)

engine = AnswerEngine(retriever=retriever)
answer = await engine.answer("What biogas yield should I expect?")
print(answer.text, [s.citation for s in answer.cited_sources])
```

Ingestion, graph building, and evaluation are importable the same way
(`ingest_entries`, `extract_graph`, `build_communities`,
`run_retrieval_eval`); see `examples/library_quickstart.py` for a
complete, runnable walkthrough.
