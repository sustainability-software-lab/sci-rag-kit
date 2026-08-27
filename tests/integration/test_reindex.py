"""Re-embed planner: find stale embeddings, re-embed exactly those.

Stale means the stored embedding_version differs from the configured
embedder's version (community summaries with no stamp count as stale).
The planner never touches rows that are already current, refuses
cross-dimension work outright (that is a migration, not a reindex), and
the dry run writes nothing.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import func, select, update

from sci_rag.db import Chunk, KgCommunity, get_session_factory
from sci_rag.embed.planner import ReindexRefused, apply_reindex, plan_reindex
from sci_rag.ingest import CorpusEntry, ingest_entries

pytestmark = pytest.mark.integration

STALE_VERSION = "old-embedder@64"


@pytest.fixture()
def corpus_entries(tmp_path: Path) -> list[CorpusEntry]:
    docs = []
    for name, text in (
        ("rice", "Rice straw availability is near 310,000 tons per year in the region."),
        ("almond", "Almond prunings are chipped in winter at 1.2 tons per acre."),
    ):
        p = tmp_path / f"{name}.md"
        p.write_text(text)
        docs.append(CorpusEntry(path=p, title=name, license_class="public", source="tests"))
    return docs


async def _age_first_chunk_and_add_community(local_embedder) -> str:  # type: ignore[no-untyped-def]
    """Mark one chunk stale and insert one community with no version stamp."""
    factory = get_session_factory()
    async with factory() as session:
        first_id = (await session.execute(select(Chunk.id).order_by(Chunk.id))).scalars().first()
        await session.execute(
            update(Chunk).where(Chunk.id == first_id).values(embedding_version=STALE_VERSION)
        )
        [vector] = await local_embedder.embed(["a cluster summary"], task="document")
        session.add(
            KgCommunity(
                title="test community",
                summary="A cluster of related concepts.",
                summary_embedding=vector,
                summary_embedding_version=None,
            )
        )
        await session.commit()
        assert first_id is not None
        return first_id


async def test_plan_reports_only_stale_rows(clean_tables, corpus_entries, local_embedder):  # type: ignore[no-untyped-def]
    await ingest_entries(corpus_entries, embedder=local_embedder)
    await _age_first_chunk_and_add_community(local_embedder)
    plan = await plan_reindex(get_session_factory(), local_embedder)
    assert plan.stale_chunks == 1
    assert plan.stale_communities == 1
    assert plan.chunk_versions == {STALE_VERSION: 1}
    assert plan.total_chunks >= 2


async def test_apply_reindexes_only_stale_and_stamps_versions(
    clean_tables, corpus_entries, local_embedder
):  # type: ignore[no-untyped-def]
    await ingest_entries(corpus_entries, embedder=local_embedder)
    stale_id = await _age_first_chunk_and_add_community(local_embedder)
    outcome = await apply_reindex(get_session_factory(), local_embedder, batch_size=1)
    assert outcome.chunks_reembedded == 1
    assert outcome.communities_reembedded == 1

    factory = get_session_factory()
    async with factory() as session:
        versions = set(
            (await session.execute(select(Chunk.embedding_version).distinct())).scalars()
        )
        assert versions == {local_embedder.version}
        stale_vector = await session.scalar(select(Chunk.embedding).where(Chunk.id == stale_id))
        assert stale_vector is not None
        community_version = await session.scalar(select(KgCommunity.summary_embedding_version))
        assert community_version == local_embedder.version


async def test_apply_skips_when_everything_current(clean_tables, corpus_entries, local_embedder):  # type: ignore[no-untyped-def]
    await ingest_entries(corpus_entries, embedder=local_embedder)
    outcome = await apply_reindex(get_session_factory(), local_embedder)
    assert outcome.chunks_reembedded == 0
    assert outcome.communities_reembedded == 0


async def test_dimension_mismatch_refused_without_writes(
    clean_tables, corpus_entries, local_embedder
):  # type: ignore[no-untyped-def]
    from sci_rag.embed.local_hash import LocalHashEmbedder

    await ingest_entries(corpus_entries, embedder=local_embedder)
    await _age_first_chunk_and_add_community(local_embedder)
    wrong_dim = LocalHashEmbedder(dim=32)
    with pytest.raises(ReindexRefused, match="dimension"):
        await plan_reindex(get_session_factory(), wrong_dim)
    with pytest.raises(ReindexRefused, match="dimension"):
        await apply_reindex(get_session_factory(), wrong_dim)
    factory = get_session_factory()
    async with factory() as session:
        stale = await session.scalar(
            select(func.count(Chunk.id)).where(Chunk.embedding_version == STALE_VERSION)
        )
    assert stale == 1  # nothing was touched


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Invoke the real CLI in a subprocess: the command spins up its own
    event loop and engine, which cannot be done inside the test loop."""
    return subprocess.run(
        [sys.executable, "-m", "sci_rag.cli.main", *args],
        capture_output=True,
        text=True,
        timeout=120,
        env=os.environ.copy(),
        cwd=Path(__file__).parents[2],
    )


async def test_cli_dry_run_reports_and_writes_nothing(clean_tables, corpus_entries, local_embedder):  # type: ignore[no-untyped-def]
    await ingest_entries(corpus_entries, embedder=local_embedder)
    await _age_first_chunk_and_add_community(local_embedder)
    result = _run_cli("embed", "reindex", "--dry-run")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "stale" in result.stdout.lower()
    factory = get_session_factory()
    async with factory() as session:
        stale = await session.scalar(
            select(func.count(Chunk.id)).where(Chunk.embedding_version == STALE_VERSION)
        )
    assert stale == 1


async def test_cli_apply_reindexes(clean_tables, corpus_entries, local_embedder):  # type: ignore[no-untyped-def]
    await ingest_entries(corpus_entries, embedder=local_embedder)
    await _age_first_chunk_and_add_community(local_embedder)
    result = _run_cli("embed", "reindex", "--apply")
    assert result.returncode == 0, result.stdout + result.stderr
    factory = get_session_factory()
    async with factory() as session:
        stale = await session.scalar(
            select(func.count(Chunk.id)).where(Chunk.embedding_version == STALE_VERSION)
        )
    assert stale == 0
