"""The re-embed planner: act on embedding version stamps.

Every chunk (and community summary) records which embedder produced its
vector. This module is what makes that stamp actionable: ``plan_reindex``
reports exactly which rows a model upgrade left behind, ``apply_reindex``
re-embeds them in batches with a commit per batch, so an interrupted run
loses at most one batch of work and is safe to just run again.

Two hard rules:

* Only stale rows are touched. Rows already stamped with the current
  embedder version are never re-embedded, which is what makes reindex
  runs cumulative and cheap.
* A dimension change is REFUSED (:class:`ReindexRefused`). The vector
  columns are created with a fixed dimension; changing it is a schema
  migration plus a full rebuild, and pretending otherwise here would
  fail halfway through with opaque database errors.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sci_rag.db.models import EMBEDDING_DIM, Chunk, KgCommunity
from sci_rag.embed.provider import EmbeddingProvider

DEFAULT_BATCH_SIZE = 32


class ReindexRefused(RuntimeError):
    """The requested reindex is not safe to run."""


@dataclass
class ReindexPlan:
    embedder_version: str
    total_chunks: int
    stale_chunks: int
    stale_communities: int
    # Stale chunk counts by their current (old) version stamp; None keys
    # render as "unstamped".
    chunk_versions: dict[str | None, int] = field(default_factory=dict)

    @property
    def clean(self) -> bool:
        return self.stale_chunks == 0 and self.stale_communities == 0


@dataclass
class ReindexOutcome:
    chunks_reembedded: int = 0
    communities_reembedded: int = 0
    batches: int = 0


def _check_dimension(embedder: EmbeddingProvider) -> None:
    if embedder.dim != EMBEDDING_DIM:
        raise ReindexRefused(
            f"embedder {embedder.version} produces {embedder.dim}-dimension vectors but the "
            f"database columns are vector({EMBEDDING_DIM}). A dimension change is a schema "
            "migration plus a full re-ingest, not a reindex. Set SCI_RAG_EMBEDDING_DIM back, "
            "or migrate the schema first."
        )


def _stale_chunks_condition(version: str):  # type: ignore[no-untyped-def]
    return (Chunk.embedding_version.is_distinct_from(version)) & (Chunk.content.is_not(None))


def _stale_communities_condition(version: str):  # type: ignore[no-untyped-def]
    return (KgCommunity.summary_embedding_version.is_distinct_from(version)) & (
        KgCommunity.summary.is_not(None)
    )


async def plan_reindex(
    session_factory: async_sessionmaker[AsyncSession], embedder: EmbeddingProvider
) -> ReindexPlan:
    _check_dimension(embedder)
    version = embedder.version
    async with session_factory() as session:
        total_chunks = (await session.scalar(select(func.count(Chunk.id)))) or 0
        rows = await session.execute(
            select(Chunk.embedding_version, func.count(Chunk.id))
            .where(_stale_chunks_condition(version))
            .group_by(Chunk.embedding_version)
        )
        chunk_versions: dict[str | None, int] = {row[0]: row[1] for row in rows}
        stale_communities = (
            await session.scalar(
                select(func.count(KgCommunity.id)).where(_stale_communities_condition(version))
            )
        ) or 0
    return ReindexPlan(
        embedder_version=version,
        total_chunks=total_chunks,
        stale_chunks=sum(chunk_versions.values()),
        stale_communities=stale_communities,
        chunk_versions=chunk_versions,
    )


async def apply_reindex(
    session_factory: async_sessionmaker[AsyncSession],
    embedder: EmbeddingProvider,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    progress: Callable[[str], None] | None = None,
) -> ReindexOutcome:
    """Re-embed stale rows in batches, committing after each batch."""
    _check_dimension(embedder)
    version = embedder.version
    outcome = ReindexOutcome()

    def report(message: str) -> None:
        if progress is not None:
            progress(message)

    while True:
        async with session_factory() as session:
            chunks = (
                (
                    await session.execute(
                        select(Chunk)
                        .where(_stale_chunks_condition(version))
                        .order_by(Chunk.id)
                        .limit(batch_size)
                    )
                )
                .scalars()
                .all()
            )
            if not chunks:
                break
            vectors = await embedder.embed([c.content for c in chunks], task="document")
            for chunk, vector in zip(chunks, vectors, strict=True):
                chunk.embedding = embedder.assert_dimension(vector)
                chunk.embedding_version = version
            await session.commit()
        outcome.chunks_reembedded += len(chunks)
        outcome.batches += 1
        report(f"chunks: {outcome.chunks_reembedded} re-embedded")

    while True:
        async with session_factory() as session:
            communities = (
                (
                    await session.execute(
                        select(KgCommunity)
                        .where(_stale_communities_condition(version))
                        .order_by(KgCommunity.id)
                        .limit(batch_size)
                    )
                )
                .scalars()
                .all()
            )
            if not communities:
                break
            summaries = [c.summary or "" for c in communities]
            vectors = await embedder.embed(summaries, task="document")
            for community, vector in zip(communities, vectors, strict=True):
                community.summary_embedding = embedder.assert_dimension(vector)
                community.summary_embedding_version = version
            await session.commit()
        outcome.communities_reembedded += len(communities)
        outcome.batches += 1
        report(f"community summaries: {outcome.communities_reembedded} re-embedded")

    return outcome
