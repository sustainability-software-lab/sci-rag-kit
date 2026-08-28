"""Seed one explicit alias duplicate for the entity-resolution benchmark.

Natural LLM extraction is stochastic and may produce no duplicates at all. A
post-resolution report requires an audit row so it cannot mislabel unchanged
state. This controlled intervention adds one clearly named same-type entity
whose alias is the selected active entity's exact name. The normal resolver
then has one deterministic alias merge to audit.

The same-state retrieval ablation runs before this script. This control exists
only for the separately reported pre/post entity-resolution condition.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sci_rag.db import EntityResolutionAudit, KgEntity, get_session_factory

CONTROL_SUFFIX = " [benchmark alias control]"


@dataclass(frozen=True)
class ResolutionControlReceipt:
    target_id: str
    target_name: str
    duplicate_id: str
    duplicate_name: str
    created: bool


async def seed_resolution_control(
    session_factory: async_sessionmaker[AsyncSession],
) -> ResolutionControlReceipt:
    """Insert or verify the single benchmark-only exact-alias duplicate."""
    async with session_factory() as session:
        audit_count = (await session.scalar(select(func.count(EntityResolutionAudit.id)))) or 0
        if audit_count:
            raise RuntimeError("resolution control must be seeded before any merge audit exists")

        entities = (
            (
                await session.execute(
                    select(KgEntity)
                    .where(KgEntity.canonical_entity_id.is_(None))
                    .order_by(KgEntity.name, KgEntity.id)
                )
            )
            .scalars()
            .all()
        )
        target = next(
            (entity for entity in entities if entity.document_ids or entity.chunk_ids),
            None,
        )
        if target is None:
            raise RuntimeError("resolution control needs an active entity with evidence")

        duplicate_name = f"{target.name}{CONTROL_SUFFIX}"
        existing = next((entity for entity in entities if entity.name == duplicate_name), None)
        if existing is not None:
            if existing.entity_type != target.entity_type or target.name not in (
                existing.aliases or []
            ):
                raise RuntimeError("existing resolution control does not match the selected target")
            return ResolutionControlReceipt(
                target.id,
                target.name,
                existing.id,
                existing.name,
                False,
            )

        duplicate = KgEntity(
            name=duplicate_name,
            entity_type=target.entity_type,
            description="Controlled exact-alias duplicate for benchmark resolution only.",
            aliases=[target.name],
            document_ids=list(target.document_ids or [])[:1],
            chunk_ids=list(target.chunk_ids or [])[:1],
        )
        session.add(duplicate)
        await session.commit()
        return ResolutionControlReceipt(
            target.id,
            target.name,
            duplicate.id,
            duplicate.name,
            True,
        )


def main() -> None:
    receipt = asyncio.run(seed_resolution_control(get_session_factory()))
    action = "created" if receipt.created else "verified"
    print(
        f"resolution control {action}: {receipt.duplicate_name!r} aliases {receipt.target_name!r}"
    )


if __name__ == "__main__":
    main()
