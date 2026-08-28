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
        duplicate = await session.scalar(
            select(KgEntity).where(KgEntity.name == receipt.duplicate_name)
        )
        audits = (await session.execute(select(EntityResolutionAudit))).scalars().all()
    assert duplicate is not None and duplicate.canonical_entity_id is not None
    assert len(audits) == 1 and audits[0].method == "alias"
