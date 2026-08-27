"""The doctor's checks against a real database, offline."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from sci_rag.cli.doctor import _run_checks
from sci_rag.db import get_engine
from sci_rag.ingest import ingest_entries, load_manifest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).parents[2]


async def _stamp_alembic_revision() -> None:
    # Tests build the schema via create_all (same DDL source as the
    # migration); the doctor reads alembic_version, so stamp it.
    async with get_engine().begin() as conn:
        await conn.execute(
            text("CREATE TABLE IF NOT EXISTS alembic_version (version_num varchar(32) PRIMARY KEY)")
        )
        await conn.execute(text("DELETE FROM alembic_version"))
        await conn.execute(text("INSERT INTO alembic_version VALUES ('0001')"))


def _by_name(checks) -> dict[str, object]:  # type: ignore[no-untyped-def]
    return {check.name: check for check in checks}


async def test_doctor_on_empty_schema(clean_tables) -> None:  # type: ignore[no-untyped-def]
    await _stamp_alembic_revision()
    checks = _by_name(await _run_checks(probe=False))

    assert checks["config"].status == "ok"
    # conftest pins local-hash + no credentials: usable, but generation is out.
    assert checks["credentials"].status == "warn"
    assert checks["domain"].status == "ok"
    assert checks["seed questions"].status == "ok"
    assert checks["database"].status == "ok"
    assert checks["pgvector"].status == "ok"
    assert checks["schema"].status == "ok"
    assert checks["embedding dimension"].status == "ok"
    assert checks["corpus"].status == "warn"
    assert "ingest" in checks["corpus"].fix


async def test_doctor_with_corpus_flags_missing_graph(clean_tables, local_embedder) -> None:  # type: ignore[no-untyped-def]
    await _stamp_alembic_revision()
    entries = load_manifest(REPO_ROOT / "data" / "demo" / "manifest.jsonl")
    await ingest_entries(entries, embedder=local_embedder)

    checks = _by_name(await _run_checks(probe=False))
    assert checks["corpus"].status == "ok"
    assert checks["knowledge graph"].status == "warn"
    assert "graph extract" in checks["knowledge graph"].fix


async def test_doctor_catches_dimension_mismatch(clean_tables, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    await _stamp_alembic_revision()
    monkeypatch.setenv("SCI_RAG_EMBEDDING_DIM", "999")
    from sci_rag.config import reset_settings_cache

    reset_settings_cache()
    try:
        checks = _by_name(await _run_checks(probe=False))
        assert checks["embedding dimension"].status == "fail"
        assert "999" in checks["embedding dimension"].detail
    finally:
        monkeypatch.delenv("SCI_RAG_EMBEDDING_DIM")
        monkeypatch.setenv("SCI_RAG_EMBEDDING_DIM", "64")
        reset_settings_cache()
