"""The benchmark's controlled alias intervention produces an auditable merge."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).parents[2]))

from scripts.seed_resolution_benchmark import seed_resolution_control

from sci_rag.db import EntityResolutionAudit, KgEntity, get_session_factory
from sci_rag.graph.resolve import resolve_entities

pytestmark = pytest.mark.integration


async def test_controlled_alias_seed_is_explicit_and_resolves_once(clean_tables) -> None:  # type: ignore[no-untyped-def]
    async with get_session_factory()() as session:
        session.add(
            KgEntity(
                id="a" * 32,
                name="rice straw",
                entity_type="Feedstock",
                aliases=[],
                document_ids=["d" * 32],
                chunk_ids=["c" * 32],
            )
        )
        await session.commit()

    receipt = await seed_resolution_control(get_session_factory())

    assert receipt.target_name == "rice straw"
    assert receipt.duplicate_name == "rice straw [benchmark alias control]"
    assert receipt.created is True

    report = await resolve_entities(get_session_factory(), dry_run=False, no_llm=True)
    assert report.automatic_pairs == 1
    assert report.merged == 1

    async with get_session_factory()() as session:
        target = await session.get(KgEntity, receipt.target_id)
        duplicate = await session.get(KgEntity, receipt.duplicate_id)
        audits = (await session.execute(select(EntityResolutionAudit))).scalars().all()
    assert target is not None and duplicate is not None
    survivor, tombstone = (
        (target, duplicate) if target.canonical_entity_id is None else (duplicate, target)
    )
    assert survivor.canonical_entity_id is None
    assert tombstone.canonical_entity_id == survivor.id
    assert len(audits) == 1
    assert audits[0].method == "alias"
    assert audits[0].merged_entity_id == tombstone.id
    assert audits[0].surviving_entity_id == survivor.id
