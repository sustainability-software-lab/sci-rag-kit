"""Graph build + graph-powered retrieval, offline via scripted mocks."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy import func, select

from sci_rag.db import Chunk, KgCommunity, KgEntity, KgRelationship, get_session_factory
from sci_rag.domain import load_domain
from sci_rag.graph import build_communities, extract_graph
from sci_rag.ingest import CorpusEntry, ingest_entries
from sci_rag.llm import LLMClient
from sci_rag.retrieve import RetrievalScope, Retriever

pytestmark = pytest.mark.integration

DOMAIN_DIR = Path(__file__).parents[2] / "domain"

EXTRACTION = {
    "entities": [
        {
            "name": "rice straw",
            "type": "Feedstock",
            "description": "post-harvest residue",
            "passages": [1],
        },
        {"name": "Colusa County", "type": "Region", "description": "rice region", "passages": [1]},
        {
            "name": "anaerobic digestion",
            "type": "ConversionProcess",
            "description": "biological conversion",
            "passages": [1],
        },
        {"name": "biogas", "type": "Product", "description": "methane-rich gas", "passages": [1]},
    ],
    "relationships": [
        {
            "source": "rice straw",
            "target": "Colusa County",
            "type": "LOCATED_IN",
            "evidence": "produced in Colusa County",
            "passage": 1,
        },
        {
            "source": "rice straw",
            "target": "anaerobic digestion",
            "type": "CONVERTED_BY",
            "evidence": "digested to biogas",
            "passage": 1,
        },
        {
            "source": "anaerobic digestion",
            "target": "biogas",
            "type": "PRODUCES",
            "evidence": "yields biogas",
            "passage": 1,
        },
        {
            "source": "biogas",
            "target": "rice straw",
            "type": "AFFECTS",
            "evidence": "creates demand for straw",
            "passage": 1,
        },
    ],
}


class ScriptedLLM(LLMClient):
    """Extraction prompts get the scripted graph; everything else gets prose."""

    def __init__(self, query_entities: list[str] | None = None) -> None:
        self.query_entities = query_entities or []

    async def generate(
        self, prompt, *, system=None, temperature=0.2, max_tokens=2048, json_mode=False
    ):  # type: ignore[no-untyped-def]
        if "knowledge graph for this domain" in prompt:
            return json.dumps(EXTRACTION)
        if '"entities"' in prompt:
            names = ", ".join(f'"{e}"' for e in self.query_entities)
            return f'{{"entities": [{names}]}}'
        return "Rice straw availability and biogas production form one connected theme."

    async def _stream_impl(self, text: str) -> AsyncIterator[str]:
        yield text

    def stream(self, prompt, *, system=None, temperature=0.2, max_tokens=2048):  # type: ignore[no-untyped-def]
        return self._stream_impl("unused")


@pytest.fixture()
def corpus(tmp_path: Path) -> list[CorpusEntry]:
    rice = tmp_path / "rice.md"
    rice.write_text(
        "# Rice Straw in Colusa County\n\nRice straw is produced in Colusa County after "
        "harvest and can be digested to biogas through anaerobic digestion."
    )
    almond = tmp_path / "almond.md"
    almond.write_text(
        "# Almond Prunings\n\nAlmond orchards are pruned each winter and the chipped "
        "prunings can be used as boiler fuel or soil amendment."
    )
    return [
        CorpusEntry(path=rice, license_class="public", source="demo"),
        CorpusEntry(path=almond, license_class="public", source="demo"),
    ]


async def _build_graph(corpus, local_embedder, llm) -> None:  # type: ignore[no-untyped-def]
    await ingest_entries(corpus, embedder=local_embedder)
    await extract_graph(
        session_factory=get_session_factory(),
        llm=llm,
        domain=load_domain(DOMAIN_DIR),
        rate_limit_s=0,
    )


async def test_extraction_populates_graph_with_provenance(clean_tables, corpus, local_embedder):  # type: ignore[no-untyped-def]
    llm = ScriptedLLM()
    await _build_graph(corpus, local_embedder, llm)

    async with get_session_factory()() as session:
        entities = (await session.execute(select(KgEntity))).scalars().all()
        relationships = (await session.execute(select(KgRelationship))).scalars().all()
        unstamped = await session.scalar(
            select(func.count(Chunk.id)).where(Chunk.graph_extracted_at.is_(None))
        )
    assert {e.name for e in entities} == {
        "rice straw",
        "Colusa County",
        "anaerobic digestion",
        "biogas",
    }
    assert all(e.chunk_ids for e in entities)
    assert len(relationships) == 4
    assert all(r.evidence for r in relationships)
    assert unstamped == 0


async def test_extraction_is_incremental_and_duplicate_safe(clean_tables, corpus, local_embedder):  # type: ignore[no-untyped-def]
    llm = ScriptedLLM()
    await _build_graph(corpus, local_embedder, llm)
    # Nothing new: a second run processes zero chunks.
    second = await extract_graph(
        session_factory=get_session_factory(),
        llm=llm,
        domain=load_domain(DOMAIN_DIR),
        rate_limit_s=0,
    )
    assert second.chunks_processed == 0
    # A forced full pass must not duplicate anything.
    third = await extract_graph(
        session_factory=get_session_factory(),
        llm=llm,
        domain=load_domain(DOMAIN_DIR),
        reprocess_all=True,
        rate_limit_s=0,
    )
    assert third.entities_created == 0
    async with get_session_factory()() as session:
        entity_count = await session.scalar(select(func.count(KgEntity.id)))
        relationship_count = await session.scalar(select(func.count(KgRelationship.id)))
    assert entity_count == 4
    assert relationship_count == 4


async def test_graph_layer_reaches_evidence_via_hops(clean_tables, corpus, local_embedder):  # type: ignore[no-untyped-def]
    llm = ScriptedLLM(query_entities=["biogas"])
    await _build_graph(corpus, local_embedder, llm)
    retriever = Retriever(
        domain=load_domain(DOMAIN_DIR),
        embedder=local_embedder,
        llm=llm,
        session_factory=get_session_factory(),
    )
    result = await retriever.retrieve(
        "what feedstock ends up as biogas", profile="deep", include_hyde=False
    )
    graph_trace = result.trace_for("graph")
    assert graph_trace is not None and graph_trace.status == "success"
    assert any("graph" in item.layers for item in result.items)


async def test_communities_build_and_serve_unrestricted_queries(
    clean_tables, corpus, local_embedder
):  # type: ignore[no-untyped-def]
    llm = ScriptedLLM()
    await _build_graph(corpus, local_embedder, llm)
    stats = await build_communities(
        session_factory=get_session_factory(),
        llm=llm,
        embedder=local_embedder,
        domain=load_domain(DOMAIN_DIR),
        min_size=2,
    )
    assert stats.communities_created >= 1
    async with get_session_factory()() as session:
        missing_embedding = await session.scalar(
            select(func.count(KgCommunity.id)).where(KgCommunity.summary_embedding.is_(None))
        )
    assert missing_embedding == 0

    retriever = Retriever(
        domain=load_domain(DOMAIN_DIR),
        embedder=local_embedder,
        llm=llm,
        session_factory=get_session_factory(),
    )
    open_result = await retriever.retrieve(
        "rice straw availability and biogas production theme",
        profile="deep",
        include_hyde=False,
        include_graph=False,
        limit=10,
    )
    community_trace = open_result.trace_for("community")
    assert community_trace is not None and community_trace.status == "success"
    assert any(item.kind == "community" for item in open_result.items)

    scoped = await retriever.retrieve(
        "rice straw availability",
        profile="deep",
        scope=RetrievalScope(license_classes=("public",)),
    )
    scoped_trace = scoped.trace_for("community")
    assert scoped_trace is not None and scoped_trace.status == "skipped"


async def test_rebuilding_communities_replaces_rather_than_appends(
    clean_tables, corpus, local_embedder
):  # type: ignore[no-untyped-def]
    llm = ScriptedLLM()
    await _build_graph(corpus, local_embedder, llm)
    for _ in range(2):
        await build_communities(
            session_factory=get_session_factory(),
            llm=llm,
            embedder=local_embedder,
            domain=load_domain(DOMAIN_DIR),
            min_size=2,
        )
    async with get_session_factory()() as session:
        count_first = await session.scalar(select(func.count(KgCommunity.id)))
    await build_communities(
        session_factory=get_session_factory(),
        llm=llm,
        embedder=local_embedder,
        domain=load_domain(DOMAIN_DIR),
        min_size=2,
    )
    async with get_session_factory()() as session:
        count_second = await session.scalar(select(func.count(KgCommunity.id)))
    assert count_first == count_second
