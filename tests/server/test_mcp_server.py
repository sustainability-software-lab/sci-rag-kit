"""MCP server tests: tool schemas, and every tool called end to end.

This is the agent smoke test: the exact tool set an agent sees, exercised
against the demo corpus through the real MCP call path.
"""

from __future__ import annotations

import json

import pytest

from sci_rag.server import build_mcp_server

pytestmark = pytest.mark.integration

EXPECTED_TOOLS = [
    "search_corpus",
    "answer_question",
    "get_document",
    "search_entities",
    "get_entity_relationships",
    "list_sources",
    "corpus_stats",
]


def _payload(result) -> dict:  # type: ignore[no-untyped-def]
    assert not result.is_error, result.content
    return json.loads(result.content[0].text)


async def test_tool_inventory_and_schemas(service) -> None:  # type: ignore[no-untyped-def]
    mcp, tools = build_mcp_server(service)
    listed = await mcp.list_tools()
    assert sorted(t.name for t in listed) == sorted(EXPECTED_TOOLS)
    assert sorted(tools) == sorted(EXPECTED_TOOLS)
    for tool in listed:
        assert tool.description and len(tool.description) > 60, (
            f"{tool.name} needs an agent-worthy description"
        )
    search = next(t for t in listed if t.name == "search_corpus")
    assert search.input_schema["required"] == ["query"]
    assert set(search.input_schema["properties"]) == {
        "query",
        "top_k",
        "deep",
        "license_classes",
        "year_min",
        "year_max",
        "journals",
    }

    resources = await mcp.list_resources()
    assert {str(r.uri) for r in resources} == {"corpus://manifest", "corpus://methodology"}


async def test_agent_smoke_every_tool(service) -> None:  # type: ignore[no-untyped-def]
    mcp, _tools = build_mcp_server(service)

    stats = _payload(await mcp.call_tool("corpus_stats", {}))
    assert stats["documents"] == 5 and stats["entities"] == 2

    sources = _payload(await mcp.call_tool("list_sources", {}))
    assert sources["sources"] == {"demo_fixture": 5}

    search = _payload(
        await mcp.call_tool(
            "search_corpus", {"query": "rice straw availability Colusa", "top_k": 3}
        )
    )
    assert search["results"], "expected search hits on the demo corpus"
    top = search["results"][0]
    assert top["document_id"] and top["citation"] and top["found_by_layers"]

    document = _payload(await mcp.call_tool("get_document", {"document_id": top["document_id"]}))
    assert document["title"].startswith("Colusa Basin")
    assert document["chunks"]

    answer = _payload(await mcp.call_tool("answer_question", {"query": "rice straw availability"}))
    assert "[1]" in answer["answer"]
    assert answer["citations"], "expected cited sources"

    entities = _payload(await mcp.call_tool("search_entities", {"name_contains": "rice"}))
    assert [e["name"] for e in entities["entities"]] == ["rice straw"]

    relationships = _payload(
        await mcp.call_tool("get_entity_relationships", {"entity_name": "RICE STRAW"})
    )
    assert relationships["found"] is True
    assert relationships["relationships"][0]["statement"] == (
        "rice straw CONVERTED_BY anaerobic digestion"
    )

    missing = _payload(
        await mcp.call_tool("get_entity_relationships", {"entity_name": "unobtainium"})
    )
    assert missing["found"] is False and "search_entities" in missing["hint"]


async def test_license_scoping_threads_through_mcp(service) -> None:  # type: ignore[no-untyped-def]
    mcp, _tools = build_mcp_server(service)
    result = _payload(
        await mcp.call_tool(
            "search_corpus",
            {"query": "rice straw", "license_classes": ["restricted"]},
        )
    )
    assert result["results"] == [], (
        "demo corpus is all public; restricted scope must return nothing"
    )


async def test_manifest_resource_matches_service(service) -> None:  # type: ignore[no-untyped-def]
    mcp, _tools = build_mcp_server(service)
    from pydantic import AnyUrl

    contents = await mcp.read_resource(AnyUrl("corpus://manifest"))
    manifest = json.loads(contents[0].content)
    assert manifest["kit"] == "sci-rag-kit"
    assert manifest["stats"]["documents"] == 5
