"""PostgreSQL proof for confidence-filtered and confidence-weighted graph walks."""

from __future__ import annotations

from pathlib import Path

import pytest

from sci_rag.db import Chunk, Document, KgEntity, KgRelationship, get_session_factory
from sci_rag.domain import load_domain
from sci_rag.retrieve.stages.graph import graph_stage
from sci_rag.retrieve.types import RetrievalScope

pytestmark = pytest.mark.integration


class SeedQueryLLM:
    async def generate_json(self, prompt: str, *, max_tokens: int = 512):  # type: ignore[no-untyped-def]
        return {"entities": ["seed"]}


async def _seed_confidence_graph(*, all_confident: bool = False) -> dict[str, str]:
    document_id = "d" * 32
    chunks = {
        "seed": "1" * 32,
        "weak": "2" * 32,
        "bridge": "3" * 32,
        "strong": "4" * 32,
    }
    entities = {
        "seed": "a" * 32,
        "weak": "b" * 32,
        "bridge": "c" * 32,
        "strong": "e" * 32,
    }
    weak_confidence = 1.0 if all_confident else 0.2
    async with get_session_factory()() as session:
        session.add(
            Document(
                id=document_id,
                title="Confidence graph evidence",
                content_hash="f" * 64,
                license_class="public",
            )
        )
        session.add_all(
            [
                Chunk(
                    id=chunk_id,
                    document_id=document_id,
                    chunk_index=index,
                    content=f"{name} evidence",
                    token_count=2,
                )
                for index, (name, chunk_id) in enumerate(chunks.items())
            ]
        )
        session.add_all(
            [
                KgEntity(
                    id=entities[name],
                    name=name,
                    entity_type="Concept",
                    document_ids=[document_id],
                    chunk_ids=[chunks[name]],
                )
                for name in chunks
            ]
        )
        session.add_all(
            [
                KgRelationship(
                    source_entity_id=entities["seed"],
                    target_entity_id=entities["weak"],
                    relation_type="RELATED_TO",
                    confidence=weak_confidence,
                    document_id=document_id,
                    chunk_id=chunks["weak"],
                ),
                KgRelationship(
                    source_entity_id=entities["seed"],
                    target_entity_id=entities["bridge"],
                    relation_type="RELATED_TO",
                    confidence=1.0 if all_confident else 0.95,
                    document_id=document_id,
                    chunk_id=chunks["bridge"],
                ),
                KgRelationship(
                    source_entity_id=entities["bridge"],
                    target_entity_id=entities["strong"],
                    relation_type="RELATED_TO",
                    confidence=1.0 if all_confident else 0.9,
                    document_id=document_id,
                    chunk_id=chunks["strong"],
                ),
            ]
        )
        await session.commit()
    return chunks


async def _walk(*, min_confidence: float, confidence_weighted: bool) -> list[str]:
    keys = await graph_stage(
        get_session_factory(),
        SeedQueryLLM(),  # type: ignore[arg-type]
        load_domain(Path(__file__).parents[2] / "domain"),
        "What follows the seed?",
        RetrievalScope(),
        limit=10,
        min_confidence=min_confidence,
        confidence_weighted=confidence_weighted,
    )
    return [chunk_id for kind, chunk_id in keys if kind == "chunk"]


async def test_threshold_filters_weak_relationships(clean_tables) -> None:  # type: ignore[no-untyped-def]
    chunks = await _seed_confidence_graph()

    unfiltered = await _walk(min_confidence=0.0, confidence_weighted=False)
    filtered = await _walk(min_confidence=0.5, confidence_weighted=False)

    assert set(unfiltered) == set(chunks.values())
    assert set(filtered) == {chunks["seed"], chunks["bridge"], chunks["strong"]}


async def test_weighting_can_rank_confident_two_hop_path_above_weak_one_hop(
    clean_tables,
) -> None:  # type: ignore[no-untyped-def]
    chunks = await _seed_confidence_graph()

    ranked = await _walk(min_confidence=0.0, confidence_weighted=True)

    assert ranked.index(chunks["strong"]) < ranked.index(chunks["weak"])


async def test_pre_confidence_corpus_is_identical_when_feature_is_off(clean_tables) -> None:  # type: ignore[no-untyped-def]
    await _seed_confidence_graph(all_confident=True)

    baseline = await _walk(min_confidence=0.0, confidence_weighted=False)
    thresholded = await _walk(min_confidence=1.0, confidence_weighted=False)

    assert thresholded == baseline
