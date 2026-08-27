"""REST contract tests: shapes, auth, scopes, rate limits, problem+json."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def test_query_returns_items_traces_and_request_id(client) -> None:  # type: ignore[no-untyped-def]
    response = await client.post(
        "/v1/query",
        json={"query": "rice straw availability in the Colusa Basin", "top_k": 5},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["items"], "expected results from the demo corpus"
    assert body["items"][0]["title"]
    assert body["items"][0]["license_class"] == "public"
    assert {t["stage"] for t in body["traces"]} == {
        "vector",
        "keyword",
        "graph",
        "community",
        "hyde",
        "rerank",
    }
    assert body["request_id"]
    assert response.headers["X-Request-ID"] == body["request_id"]


async def test_query_can_omit_content(client) -> None:  # type: ignore[no-untyped-def]
    response = await client.post(
        "/v1/query", json={"query": "rice straw", "include_content": False}
    )
    assert response.status_code == 200
    assert all(item["content"] is None for item in response.json()["items"])


async def test_validation_errors_are_problem_json(client) -> None:  # type: ignore[no-untyped-def]
    response = await client.post("/v1/query", json={"query": ""})
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "invalid_request"


async def test_missing_key_is_401_with_www_authenticate(secured_client) -> None:  # type: ignore[no-untyped-def]
    response = await secured_client.post("/v1/query", json={"query": "rice"})
    assert response.status_code == 401
    assert response.json()["code"] == "missing_key"
    assert response.headers["WWW-Authenticate"] == "Bearer"


async def test_unknown_key_is_401(secured_client) -> None:  # type: ignore[no-untyped-def]
    response = await secured_client.post(
        "/v1/query", json={"query": "rice"}, headers={"Authorization": "Bearer nope"}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_key"


async def test_scope_enforcement(secured_client) -> None:  # type: ignore[no-untyped-def]
    ok = await secured_client.post(
        "/v1/query", json={"query": "rice"}, headers={"Authorization": "Bearer query-key"}
    )
    assert ok.status_code == 200
    forbidden = await secured_client.get(
        "/v1/documents", headers={"Authorization": "Bearer query-key"}
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "insufficient_scope"


async def test_rate_limit_returns_429_with_retry_after(secured_client) -> None:  # type: ignore[no-untyped-def]
    headers = {"Authorization": "Bearer limited-key"}
    for _ in range(2):
        assert (
            await secured_client.post("/v1/query", json={"query": "rice"}, headers=headers)
        ).status_code == 200
    third = await secured_client.post("/v1/query", json={"query": "rice"}, headers=headers)
    assert third.status_code == 429
    assert third.json()["code"] == "rate_limited"
    assert int(third.headers["Retry-After"]) >= 1


async def test_corpus_manifest_is_public_even_when_auth_is_on(secured_client) -> None:  # type: ignore[no-untyped-def]
    response = await secured_client.get("/v1/corpus-manifest")
    assert response.status_code == 200
    manifest = response.json()
    assert manifest["kit"] == "sci-rag-kit"
    assert manifest["stats"]["documents"] == 5
    assert manifest["retrieval"]["fusion"] == "weighted_rrf"
    assert manifest["endpoints"]["mcp"].endswith("/mcp")


async def test_mcp_mount_requires_auth_when_keys_configured(secured_client) -> None:  # type: ignore[no-untyped-def]
    # Note the trailing slash: the parent router 307-redirects bare /mcp
    # before the mount (and its auth wrapper) ever runs.
    response = await secured_client.post("/mcp/", json={})
    assert response.status_code == 401
    assert response.json()["code"] == "missing_key"


async def test_health_and_status(client) -> None:  # type: ignore[no-untyped-def]
    health = await client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["database"] is True

    status = await client.get("/v1/status")
    assert status.status_code == 200
    body = status.json()
    assert body["documents"] == 5
    assert body["entities"] == 2
    assert body["license_classes"] == {"public": 5}


async def test_documents_catalog_and_detail(client) -> None:  # type: ignore[no-untyped-def]
    listing = await client.get("/v1/documents", params={"search": "rice"})
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] == 1
    document = body["documents"][0]
    assert document["title"].startswith("Colusa Basin Rice Straw")

    detail = await client.get(f"/v1/documents/{document['id']}")
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["chunks"], "expected chunk previews"
    assert detail_body["formatted_citation"]

    missing = await client.get("/v1/documents/doesnotexist")
    assert missing.status_code == 404
    assert missing.json()["code"] == "document_not_found"
