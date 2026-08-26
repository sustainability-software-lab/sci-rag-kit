"""Layer 3: knowledge-graph traversal.

The question names entities; the graph knows their neighbors; the
neighbors point back to evidence chunks. Concretely:

1. A fast LLM call extracts entity names from the question.
2. Matching graph entities are walked up to two hops in either direction.
3. The chunks those entities were extracted from re-enter the candidate
   pool, ranked by hop distance.

This is what makes multi-hop questions work ("what converts the residue
that almonds produce?"): the connecting entity brings its evidence with it
even when the question's own words never appear in that text.
"""

from __future__ import annotations

import structlog
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql.sqltypes import Text as TextType

from sci_rag.db.models import Chunk, Document
from sci_rag.domain import DomainProfile
from sci_rag.llm import LLMClient
from sci_rag.retrieve.types import Key, RetrievalScope, scope_conditions

log = structlog.get_logger(__name__)

MAX_HOPS = 2

_WALK_SQL = text(
    """
    WITH RECURSIVE walk(entity_id, hop) AS (
        SELECT id, 0 FROM kg_entities WHERE lower(name) = ANY(:names)
        UNION
        SELECT CASE WHEN r.source_entity_id = w.entity_id
                    THEN r.target_entity_id ELSE r.source_entity_id END,
               w.hop + 1
        FROM kg_relationships r
        JOIN walk w ON w.entity_id IN (r.source_entity_id, r.target_entity_id)
        WHERE w.hop < :max_hops
    )
    SELECT e.chunk_ids, MIN(w.hop) AS hop
    FROM walk w
    JOIN kg_entities e ON e.id = w.entity_id
    GROUP BY e.id, e.chunk_ids
    ORDER BY hop, e.id
    """
).bindparams(bindparam("names", type_=ARRAY(TextType())))


async def extract_query_entities(llm: LLMClient, domain: DomainProfile, query: str) -> list[str]:
    prompt = domain.render_prompt(
        "query_entities",
        DOMAIN_NAME=domain.name,
        QUERY=query,
        ENTITY_TYPES=domain.entity_types_block(),
    )
    try:
        payload = await llm.generate_json(prompt, max_tokens=512)
    except Exception as exc:
        log.warning("query_entity_extraction_failed", error=type(exc).__name__)
        return []
    entities = payload.get("entities", []) if isinstance(payload, dict) else []
    return [str(name).strip() for name in entities if str(name).strip()][:15]


async def graph_stage(
    session_factory: async_sessionmaker[AsyncSession],
    llm: LLMClient,
    domain: DomainProfile,
    query: str,
    scope: RetrievalScope,
    limit: int,
) -> list[Key]:
    names = await extract_query_entities(llm, domain, query)
    if not names:
        return []
    lowered = sorted({name.lower() for name in names})

    async with session_factory() as session:
        rows = (await session.execute(_WALK_SQL, {"names": lowered, "max_hops": MAX_HOPS})).all()
        # Collect candidate chunk ids in hop order, closest entities first.
        ordered_chunk_ids: list[str] = []
        seen: set[str] = set()
        for chunk_ids, _hop in rows:
            for chunk_id in chunk_ids or []:
                if chunk_id not in seen:
                    seen.add(chunk_id)
                    ordered_chunk_ids.append(chunk_id)
        if not ordered_chunk_ids:
            return []

        # Resolve against the caller's scope; scope always precedes ranking.
        from sqlalchemy import select

        eligible = set(
            (
                await session.execute(
                    select(Chunk.id)
                    .join(Document, Chunk.document_id == Document.id)
                    .where(Chunk.id.in_(ordered_chunk_ids), *scope_conditions(scope))
                )
            ).scalars()
        )

    results = [cid for cid in ordered_chunk_ids if cid in eligible][:limit]
    return [("chunk", chunk_id) for chunk_id in results]
