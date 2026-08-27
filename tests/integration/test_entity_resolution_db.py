from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select

from sci_rag.db import (
    Chunk,
    Document,
    EntityResolutionAudit,
    KgCommunity,
    KgEntity,
    KgRelationship,
    get_session_factory,
)
from sci_rag.domain import load_domain
from sci_rag.graph.resolve import resolve_entities
from sci_rag.retrieve.stages.graph import graph_stage
from sci_rag.retrieve.types import RetrievalScope

pytestmark = pytest.mark.integration


async def seed_duplicates() -> dict[str, str]:
    async with get_session_factory()() as session:
        document = Document(
            id="d" * 32,
            title="Rice evidence",
            content_hash="f" * 64,
            license_class="public",
        )
        chunk = Chunk(
            id="c" * 32,
            document_id=document.id,
            chunk_index=0,
            content="Paddy straw can be converted.",
            token_count=6,
        )
        winner = KgEntity(
            id="a" * 32,
            name="rice straw",
            entity_type="Feedstock",
            aliases=["paddy straw"],
            document_ids=[document.id],
            chunk_ids=[],
        )
        loser = KgEntity(
            id="b" * 32,
            name="Paddy Straw",
            entity_type="Feedstock",
            aliases=[],
            document_ids=[],
            chunk_ids=[chunk.id],
        )
        neighbor = KgEntity(
            id="e" * 32,
            name="anaerobic digestion",
            entity_type="ConversionProcess",
            aliases=[],
            document_ids=[document.id],
            chunk_ids=[chunk.id],
        )
        relationship = KgRelationship(
            id="r" * 32,
            source_entity_id=loser.id,
            target_entity_id=neighbor.id,
            relation_type="CONVERTED_BY",
            confidence=0.8,
            chunk_id=chunk.id,
            document_id=document.id,
        )
        session.add_all([document, chunk, winner, loser, neighbor, relationship])
        await session.commit()
    return {"winner": winner.id, "loser": loser.id, "chunk": chunk.id, "rel": relationship.id}


async def test_resolution_merges_evidence_repoints_edges_and_audits(clean_tables) -> None:  # type: ignore[no-untyped-def]
    ids = await seed_duplicates()

    report = await resolve_entities(get_session_factory(), dry_run=False, no_llm=True)

    assert report.merged == 1
    async with get_session_factory()() as session:
        winner = await session.get(KgEntity, ids["winner"])
        loser = await session.get(KgEntity, ids["loser"])
        relationship = await session.get(KgRelationship, ids["rel"])
        audits = (await session.execute(select(EntityResolutionAudit))).scalars().all()
    assert winner is not None and loser is not None and relationship is not None
    assert winner.document_ids == ["d" * 32]
    assert winner.chunk_ids == [ids["chunk"]]
    assert "Paddy Straw" in winner.aliases
    assert loser.canonical_entity_id == winner.id
    assert relationship.source_entity_id == winner.id
    assert len(audits) == 1
    assert audits[0].merged_entity_name == "Paddy Straw"
    assert audits[0].surviving_entity_name == "rice straw"
    assert audits[0].method == "alias"


async def test_resolution_dry_run_makes_no_writes(clean_tables) -> None:  # type: ignore[no-untyped-def]
    await seed_duplicates()

    report = await resolve_entities(get_session_factory(), dry_run=True, no_llm=True)

    async with get_session_factory()() as session:
        canonical_count = await session.scalar(
            select(func.count(KgEntity.id)).where(KgEntity.canonical_entity_id.is_not(None))
        )
        audit_count = await session.scalar(select(func.count(EntityResolutionAudit.id)))
    assert report.planned_merges == 1
    assert report.merged == 0
    assert canonical_count == 0
    assert audit_count == 0


async def test_resolution_deduplicates_affected_edges_and_invalidates_communities(
    clean_tables,
) -> None:  # type: ignore[no-untyped-def]
    ids = await seed_duplicates()
    async with get_session_factory()() as session:
        session.add_all(
            [
                KgRelationship(
                    id="s" * 32,
                    source_entity_id=ids["winner"],
                    target_entity_id="e" * 32,
                    relation_type="CONVERTED_BY",
                    confidence=0.95,
                ),
                KgCommunity(
                    id="m" * 32,
                    title="Rice conversion",
                    level=0,
                    member_entity_ids=[ids["loser"], "e" * 32],
                    summary="Paddy straw and digestion.",
                ),
            ]
        )
        await session.commit()

    await resolve_entities(get_session_factory(), dry_run=False, no_llm=True)

    async with get_session_factory()() as session:
        relationships = (
            (
                await session.execute(
                    select(KgRelationship).where(
                        KgRelationship.source_entity_id == ids["winner"],
                        KgRelationship.target_entity_id == "e" * 32,
                        KgRelationship.relation_type == "CONVERTED_BY",
                    )
                )
            )
            .scalars()
            .all()
        )
        community_count = await session.scalar(select(func.count(KgCommunity.id)))
    assert len(relationships) == 1
    assert relationships[0].confidence == 0.95
    assert community_count == 0


class QueryLLM:
    async def generate_json(self, prompt: str, *, max_tokens: int = 512):  # type: ignore[no-untyped-def]
        return {"entities": ["Paddy Straw"]}


class ExactQueryLLM:
    async def generate_json(self, prompt: str, *, max_tokens: int = 512):  # type: ignore[no-untyped-def]
        return {"entities": ["seed process"]}


async def test_traversal_by_merged_name_reaches_survivor_evidence(clean_tables) -> None:  # type: ignore[no-untyped-def]
    ids = await seed_duplicates()
    await resolve_entities(get_session_factory(), dry_run=False, no_llm=True)

    keys = await graph_stage(
        get_session_factory(),
        QueryLLM(),  # type: ignore[arg-type]
        load_domain(Path(__file__).parents[2] / "domain"),
        "What converts paddy straw?",
        RetrievalScope(),
        limit=5,
    )

    assert ("chunk", ids["chunk"]) in keys


async def test_scoped_traversal_does_not_expand_unproven_aliases(clean_tables) -> None:  # type: ignore[no-untyped-def]
    await seed_duplicates()
    await resolve_entities(get_session_factory(), dry_run=False, no_llm=True)

    keys = await graph_stage(
        get_session_factory(),
        QueryLLM(),  # type: ignore[arg-type]
        load_domain(Path(__file__).parents[2] / "domain"),
        "What converts paddy straw?",
        RetrievalScope(license_classes=("public",)),
        limit=5,
    )

    assert keys == []


async def test_scoped_traversal_rejects_edges_evidenced_only_by_restricted_document(
    clean_tables,
) -> None:  # type: ignore[no-untyped-def]
    public_seed_doc = "1" * 32
    public_neighbor_doc = "2" * 32
    restricted_edge_doc = "3" * 32
    seed_chunk = "4" * 32
    neighbor_chunk = "5" * 32
    edge_chunk = "6" * 32
    seed_entity = "7" * 32
    neighbor_entity = "8" * 32
    async with get_session_factory()() as session:
        session.add_all(
            [
                Document(
                    id=public_seed_doc,
                    title="Public seed",
                    content_hash="1" * 64,
                    license_class="public",
                ),
                Document(
                    id=public_neighbor_doc,
                    title="Public neighbor",
                    content_hash="2" * 64,
                    license_class="public",
                ),
                Document(
                    id=restricted_edge_doc,
                    title="Restricted edge evidence",
                    content_hash="3" * 64,
                    license_class="restricted",
                ),
                Chunk(
                    id=seed_chunk,
                    document_id=public_seed_doc,
                    chunk_index=0,
                    content="Seed evidence.",
                    token_count=2,
                ),
                Chunk(
                    id=neighbor_chunk,
                    document_id=public_neighbor_doc,
                    chunk_index=0,
                    content="Neighbor evidence.",
                    token_count=2,
                ),
                Chunk(
                    id=edge_chunk,
                    document_id=restricted_edge_doc,
                    chunk_index=0,
                    content="Restricted relationship evidence.",
                    token_count=3,
                ),
                KgEntity(
                    id=seed_entity,
                    name="seed process",
                    entity_type="ConversionProcess",
                    aliases=[],
                    document_ids=[public_seed_doc],
                    chunk_ids=[seed_chunk],
                ),
                KgEntity(
                    id=neighbor_entity,
                    name="neighbor product",
                    entity_type="Product",
                    aliases=[],
                    document_ids=[public_neighbor_doc],
                    chunk_ids=[neighbor_chunk],
                ),
                KgRelationship(
                    source_entity_id=seed_entity,
                    target_entity_id=neighbor_entity,
                    relation_type="PRODUCES",
                    document_id=restricted_edge_doc,
                    chunk_id=edge_chunk,
                ),
            ]
        )
        await session.commit()

    keys = await graph_stage(
        get_session_factory(),
        ExactQueryLLM(),  # type: ignore[arg-type]
        load_domain(Path(__file__).parents[2] / "domain"),
        "What does the seed process produce?",
        RetrievalScope(license_classes=("public",)),
        limit=5,
    )

    assert ("chunk", seed_chunk) in keys
    assert ("chunk", neighbor_chunk) not in keys


async def test_graph_gc_preserves_resolution_tombstones(clean_tables) -> None:  # type: ignore[no-untyped-def]
    from sci_rag.corpus import graph_gc

    ids = await seed_duplicates()
    await resolve_entities(get_session_factory(), dry_run=False, no_llm=True)

    outcome = await graph_gc(get_session_factory(), dry_run=False)

    async with get_session_factory()() as session:
        loser = await session.get(KgEntity, ids["loser"])
    assert loser is not None
    assert loser.canonical_entity_id == ids["winner"]
    assert outcome.entities_deleted == 0


async def test_graph_gc_preserves_empty_survivor_referenced_by_tombstone(clean_tables) -> None:  # type: ignore[no-untyped-def]
    from sci_rag.corpus import graph_gc

    ids = await seed_duplicates()
    await resolve_entities(get_session_factory(), dry_run=False, no_llm=True)
    async with get_session_factory()() as session:
        winner = await session.get(KgEntity, ids["winner"])
        assert winner is not None
        winner.document_ids = []
        winner.chunk_ids = []
        await session.commit()

    outcome = await graph_gc(get_session_factory(), dry_run=False)

    async with get_session_factory()() as session:
        winner = await session.get(KgEntity, ids["winner"])
        loser = await session.get(KgEntity, ids["loser"])
    assert outcome.entities_deleted == 0
    assert winner is not None and loser is not None
    assert loser.canonical_entity_id == winner.id
