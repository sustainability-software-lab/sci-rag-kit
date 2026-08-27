# API reference

One server, two front doors, one service behind both. Start it with
`sci-rag serve`; interactive OpenAPI docs live at `/docs`.

## Authentication

Send `Authorization: Bearer <key>`. Keys are configured by the operator
as a JSON map in `SCI_RAG_API_KEYS`:

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

Request fields: `query` (required), `top_k` (1..50, default 8),
`profile` (`interactive` default, or `deep`), per-layer overrides
(`include_graph`, `include_community`, `include_hyde`),
`license_classes` and `sources` allowlists (omit for all; an empty
license list returns nothing by design), `include_content: false` for
lean responses.

The response carries `items` (each with title, section path, citation,
license class, fused score, and `layers`, which names the layers that
found it), `traces` (per-stage status and timing), and
`degraded_stages`. If something timed out, you will know exactly what.

### POST /v1/answer

A grounded, cited answer. Two modes in one endpoint:

**Streaming (default).** `"stream": true` returns Server-Sent Events:

```
event: retrieval_started   data: {"profile": "deep"}
event: retrieval_done      data: {"item_count": 8, "degraded_stages": [], "traces": [...]}
event: generation_started  data: {"model": "gemini-2.5-flash"}
event: delta               data: {"text": "Given its ash content, ..."}   (repeats)
event: citations           data: {"citations": [{"index": 1, "title": "...", "cited": true, ...}]}
event: done                data: {"finish_reason": "stop"}
```

An `error` event (`code`, `message`) replaces the tail on failure.

**JSON.** `"stream": false` returns one body: `answer`, `model`,
`citations` (with a `cited` flag per source), `traces`,
`degraded_stages`.

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

The seven tools:

| Tool | Use it to |
|------|-----------|
| `search_corpus(query, top_k, deep, license_classes)` | get ranked evidence chunks to reason over yourself |
| `answer_question(query, top_k, license_classes)` | get a grounded answer with numbered citations |
| `get_document(document_id)` | inspect a cited source: metadata, license, chunk previews |
| `search_entities(name_contains, entity_type, limit)` | find knowledge-graph entities by name |
| `get_entity_relationships(entity_name)` | see every stated relationship of an entity, with evidence quotes |
| `list_sources()` | learn the corpus's source buckets and license mix |
| `corpus_stats()` | size and shape; a fast "is this corpus worth querying" check |

Plus two resources: `corpus://manifest` (same payload as the REST
manifest) and `corpus://methodology` (how retrieval works here, one
page). Tool descriptions are written for the agent reading them; if you
add tools, hold that bar.

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
    scope=RetrievalScope(license_classes=("public", "open_commercial")),
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
