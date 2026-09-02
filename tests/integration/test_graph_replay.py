"""Record and replay the demo graph through fresh database identities."""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

import pytest
from scripts.graph_replay import (
    GraphReplayError,
    ReplayArtifact,
    run_graph_replay,
    write_candidate,
)
from sqlalchemy import func, select, text

from sci_rag.db import (
    Chunk,
    Document,
    EntityResolutionAudit,
    KgEntity,
    KgRelationship,
    get_session_factory,
)
from sci_rag.domain import load_domain
from sci_rag.llm import LLMClient

pytestmark = pytest.mark.integration

DOMAIN_DIR = Path(__file__).parents[2] / "domain"
EXTRACTION_MODEL = "test:scripted-extraction"
EXTRACTION = json.dumps(
    {
        "entities": [
            {
                "name": "alpha feedstock",
                "type": "Feedstock",
                "description": "a synthetic residue",
                "passages": [1],
            },
            {
                "name": "beta region",
                "type": "Region",
                "description": "a synthetic region",
                "passages": [2],
            },
        ],
        "relationships": [
            {
                "source": "alpha feedstock",
                "target": "beta region",
                "type": "LOCATED_IN",
                "evidence": "synthetic location evidence",
                "passage": 1,
                "confidence": 0.9,
            }
        ],
    }
)


class ScriptedExtractionLLM(LLMClient):
    model = EXTRACTION_MODEL

    def __init__(self) -> None:
        self.call_count = 0

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        json_mode: bool = False,
    ) -> str:
        self.call_count += 1
        return EXTRACTION

    async def _stream(self) -> AsyncIterator[str]:
        yield "unused"

    def stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        return self._stream()


class InvalidExtractionLLM(ScriptedExtractionLLM):
    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        json_mode: bool = False,
    ) -> str:
        return "not valid JSON"


async def _seed_demo(
    *,
    first_ids: tuple[str, str],
    second_ids: tuple[str, str],
    source: str = "demo_fixture",
    license_class: str = "public",
    stamped: bool = False,
    graph_row: bool = False,
    with_chunks: bool = True,
    audit_row: bool = False,
) -> None:
    documents = (
        ("Alpha fixture", "Alpha is a synthetic agricultural residue.", first_ids),
        ("Beta fixture", "Beta is a synthetic agricultural region.", second_ids),
    )
    async with get_session_factory()() as session:
        for title, content, (document_id, chunk_id) in documents:
            session.add(
                Document(
                    id=document_id,
                    title=title,
                    source=source,
                    license_class=license_class,
                    content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                    chunk_count=int(with_chunks),
                )
            )
            if with_chunks:
                session.add(
                    Chunk(
                        id=chunk_id,
                        document_id=document_id,
                        chunk_index=0,
                        content=content,
                        token_count=len(content.split()),
                        graph_extracted_at=datetime.now(UTC) if stamped else None,
                    )
                )
        if graph_row:
            session.add(
                KgEntity(
                    id="e" * 32,
                    name="preexisting graph state",
                    entity_type="Feedstock",
                    aliases=[],
                    document_ids=[],
                    chunk_ids=[],
                )
            )
        if audit_row:
            session.add(
                EntityResolutionAudit(
                    id="a" * 32,
                    merged_entity_id="b" * 32,
                    merged_entity_name="merged",
                    surviving_entity_id="c" * 32,
                    surviving_entity_name="survivor",
                    method="test",
                    confidence=1.0,
                )
            )
        await session.commit()


async def _reset_database(database) -> None:  # type: ignore[no-untyped-def]
    async with database.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE documents, chunks, document_citations, kg_entities, "
                "kg_relationships, kg_communities, entity_resolution_audit CASCADE"
            )
        )


async def test_record_and_require_replay_survive_fresh_database_ids(
    clean_tables, database, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    await _seed_demo(
        first_ids=("1" * 32, "3" * 32),
        second_ids=("2" * 32, "4" * 32),
    )
    artifact_dir = tmp_path / "artifacts"
    record_receipt = tmp_path / "record-receipt.json"

    recorded = await run_graph_replay(
        mode="refresh",
        artifact_dir=artifact_dir,
        receipt_path=record_receipt,
        session_factory=get_session_factory(),
        domain=load_domain(DOMAIN_DIR),
        extraction_model=EXTRACTION_MODEL,
        llm_factory=ScriptedExtractionLLM,
        source_commit="record-commit",
        batch_size=2,
        rate_limit_s=0,
    )

    assert recorded.mode == "refresh"
    assert recorded.extracted_calls == 1
    assert recorded.replayed_calls == 0
    assert recorded.artifact_path.is_file()
    assert record_receipt.is_file()

    await _reset_database(database)
    # The same content now has fresh persistence ids whose lexical order is reversed.
    await _seed_demo(
        first_ids=("9" * 32, "7" * 32),
        second_ids=("8" * 32, "6" * 32),
    )
    provider_constructions = 0

    def forbidden_provider() -> LLMClient:
        nonlocal provider_constructions
        provider_constructions += 1
        raise AssertionError("strict replay constructed a live provider")

    replay_receipt = tmp_path / "replay-receipt.json"
    replayed = await run_graph_replay(
        mode="require",
        artifact_path=recorded.artifact_path,
        receipt_path=replay_receipt,
        session_factory=get_session_factory(),
        domain=load_domain(DOMAIN_DIR),
        extraction_model=EXTRACTION_MODEL,
        llm_factory=forbidden_provider,
        batch_size=2,
        rate_limit_s=0,
    )

    assert provider_constructions == 0
    assert replayed.mode == "require"
    assert replayed.extracted_calls == 0
    assert replayed.replayed_calls == recorded.extracted_calls
    assert replayed.artifact_sha256 == recorded.artifact_sha256
    assert replayed.corpus_digest == recorded.corpus_digest
    assert replayed.domain_digest == recorded.domain_digest
    assert replayed.graph_digest == recorded.graph_digest
    assert replayed.entity_count == recorded.entity_count
    assert replayed.relationship_count == recorded.relationship_count
    assert replay_receipt.is_file()


@pytest.mark.parametrize(
    (
        "source",
        "license_class",
        "stamped",
        "graph_row",
        "with_chunks",
        "audit_row",
        "reason",
    ),
    [
        ("local", "public", False, False, True, False, "demo_fixture"),
        ("demo_fixture", "restricted", False, False, True, False, "public"),
        ("demo_fixture", "public", True, False, True, False, "unstamped"),
        ("demo_fixture", "public", False, True, True, False, "graph"),
        ("demo_fixture", "public", False, False, False, False, "chunk"),
        ("demo_fixture", "public", False, False, True, True, "graph"),
    ],
)
async def test_refresh_refuses_a_target_outside_the_pristine_public_demo_boundary(
    clean_tables,
    tmp_path: Path,
    source: str,
    license_class: str,
    stamped: bool,
    graph_row: bool,
    with_chunks: bool,
    audit_row: bool,
    reason: str,
) -> None:  # type: ignore[no-untyped-def]
    await _seed_demo(
        first_ids=("1" * 32, "3" * 32),
        second_ids=("2" * 32, "4" * 32),
        source=source,
        license_class=license_class,
        stamped=stamped,
        graph_row=graph_row,
        with_chunks=with_chunks,
        audit_row=audit_row,
    )
    provider_constructions = 0

    def provider() -> LLMClient:
        nonlocal provider_constructions
        provider_constructions += 1
        return ScriptedExtractionLLM()

    artifact_dir = tmp_path / "artifacts"
    receipt_path = tmp_path / "receipt.json"
    with pytest.raises(GraphReplayError, match=reason):
        await run_graph_replay(
            mode="refresh",
            artifact_dir=artifact_dir,
            receipt_path=receipt_path,
            session_factory=get_session_factory(),
            domain=load_domain(DOMAIN_DIR),
            extraction_model=EXTRACTION_MODEL,
            llm_factory=provider,
            source_commit="record-commit",
            batch_size=2,
            rate_limit_s=0,
        )

    assert provider_constructions == 0
    assert not artifact_dir.exists()
    assert not receipt_path.exists()
    async with get_session_factory()() as session:
        entity_count = await session.scalar(select(func.count(KgEntity.id)))
        relationship_count = await session.scalar(select(func.count(KgRelationship.id)))
    assert entity_count == int(graph_row)
    assert relationship_count == 0


async def test_require_rejects_identity_drift_without_constructing_a_provider(
    clean_tables, database, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    await _seed_demo(
        first_ids=("1" * 32, "3" * 32),
        second_ids=("2" * 32, "4" * 32),
    )
    recorded = await run_graph_replay(
        mode="refresh",
        artifact_dir=tmp_path / "artifacts",
        receipt_path=tmp_path / "record-receipt.json",
        session_factory=get_session_factory(),
        domain=load_domain(DOMAIN_DIR),
        extraction_model=EXTRACTION_MODEL,
        llm_factory=ScriptedExtractionLLM,
        source_commit="record-commit",
        batch_size=2,
        rate_limit_s=0,
    )
    await _reset_database(database)
    await _seed_demo(
        first_ids=("9" * 32, "7" * 32),
        second_ids=("8" * 32, "6" * 32),
    )
    provider_constructions = 0

    def forbidden_provider() -> LLMClient:
        nonlocal provider_constructions
        provider_constructions += 1
        raise AssertionError("identity drift constructed a live provider")

    with pytest.raises(GraphReplayError, match="extraction model"):
        await run_graph_replay(
            mode="require",
            artifact_path=recorded.artifact_path,
            receipt_path=tmp_path / "drift-receipt.json",
            session_factory=get_session_factory(),
            domain=load_domain(DOMAIN_DIR),
            extraction_model="test:a-different-model",
            llm_factory=forbidden_provider,
            batch_size=2,
            rate_limit_s=0,
        )

    assert provider_constructions == 0
    async with get_session_factory()() as session:
        entity_count = await session.scalar(select(func.count(KgEntity.id)))
        relationship_count = await session.scalar(select(func.count(KgRelationship.id)))
    assert entity_count == 0
    assert relationship_count == 0


async def test_failed_refresh_writes_neither_candidate_nor_receipt(
    clean_tables, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    await _seed_demo(
        first_ids=("1" * 32, "3" * 32),
        second_ids=("2" * 32, "4" * 32),
    )
    artifact_dir = tmp_path / "artifacts"
    receipt_path = tmp_path / "receipt.json"

    with pytest.raises(GraphReplayError, match="incomplete"):
        await run_graph_replay(
            mode="refresh",
            artifact_dir=artifact_dir,
            receipt_path=receipt_path,
            session_factory=get_session_factory(),
            domain=load_domain(DOMAIN_DIR),
            extraction_model=EXTRACTION_MODEL,
            llm_factory=InvalidExtractionLLM,
            source_commit="record-commit",
            batch_size=2,
            rate_limit_s=0,
        )

    assert not artifact_dir.exists()
    assert not receipt_path.exists()


async def test_off_mode_counts_live_calls_without_writing_an_artifact(
    clean_tables, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    await _seed_demo(
        first_ids=("1" * 32, "3" * 32),
        second_ids=("2" * 32, "4" * 32),
    )
    receipt_path = tmp_path / "receipt.json"

    receipt = await run_graph_replay(
        mode="off",
        receipt_path=receipt_path,
        session_factory=get_session_factory(),
        domain=load_domain(DOMAIN_DIR),
        extraction_model=EXTRACTION_MODEL,
        llm_factory=ScriptedExtractionLLM,
        batch_size=2,
        rate_limit_s=0,
    )

    assert receipt.extracted_calls == 1
    assert receipt.replayed_calls == 0
    assert receipt.artifact_path is None
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert payload["extracted_call_count"] == 1
    assert payload["artifact_path"] is None


async def test_require_rejects_an_artifact_that_declares_failed_batches(
    clean_tables, database, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    await _seed_demo(
        first_ids=("1" * 32, "3" * 32),
        second_ids=("2" * 32, "4" * 32),
    )
    recorded = await run_graph_replay(
        mode="refresh",
        artifact_dir=tmp_path / "recorded",
        receipt_path=tmp_path / "record-receipt.json",
        session_factory=get_session_factory(),
        domain=load_domain(DOMAIN_DIR),
        extraction_model=EXTRACTION_MODEL,
        llm_factory=ScriptedExtractionLLM,
        source_commit="record-commit",
        batch_size=2,
        rate_limit_s=0,
    )
    raw = json.loads(recorded.artifact_path.read_text(encoding="utf-8"))
    raw["failed_batches"] = 1
    incomplete_path = write_candidate(ReplayArtifact.from_dict(raw), tmp_path / "incomplete")

    await _reset_database(database)
    await _seed_demo(
        first_ids=("9" * 32, "7" * 32),
        second_ids=("8" * 32, "6" * 32),
    )
    provider_constructions = 0

    def forbidden_provider() -> LLMClient:
        nonlocal provider_constructions
        provider_constructions += 1
        raise AssertionError("incomplete artifact constructed a provider")

    with pytest.raises(GraphReplayError, match="failed batches"):
        await run_graph_replay(
            mode="require",
            artifact_path=incomplete_path,
            receipt_path=tmp_path / "incomplete-receipt.json",
            session_factory=get_session_factory(),
            domain=load_domain(DOMAIN_DIR),
            extraction_model=EXTRACTION_MODEL,
            llm_factory=forbidden_provider,
            batch_size=2,
            rate_limit_s=0,
        )

    assert provider_constructions == 0
    assert not (tmp_path / "incomplete-receipt.json").exists()


async def test_refresh_rejects_a_mislabeled_provider_before_its_first_call(
    clean_tables, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    await _seed_demo(
        first_ids=("1" * 32, "3" * 32),
        second_ids=("2" * 32, "4" * 32),
    )
    provider = ScriptedExtractionLLM()
    artifact_dir = tmp_path / "artifacts"
    receipt_path = tmp_path / "receipt.json"

    with pytest.raises(GraphReplayError, match="effective extraction model"):
        await run_graph_replay(
            mode="refresh",
            artifact_dir=artifact_dir,
            receipt_path=receipt_path,
            session_factory=get_session_factory(),
            domain=load_domain(DOMAIN_DIR),
            extraction_model="test:mislabeled-model",
            llm_factory=lambda: provider,
            source_commit="record-commit",
            batch_size=2,
            rate_limit_s=0,
        )

    assert provider.call_count == 0
    assert not artifact_dir.exists()
    assert not receipt_path.exists()
