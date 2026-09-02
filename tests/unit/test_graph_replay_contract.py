"""The committed benchmark graph replay artifact contract fails closed."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

sys.path.insert(0, str(Path(__file__).parents[2]))

import pytest
from scripts.graph_replay import (
    GraphReplayError,
    ReplayArtifact,
    ReplayCall,
    ReplayLLM,
    _canonical_graph,
    artifact_sha256,
    call_input_digest,
    write_candidate,
)

GENERATION_PARAMETERS = {"temperature": 0.0, "json_mode": True, "max_tokens": 8192}
RAW_COMPLETION = '{"entities": [], "relationships": []}'


def _recorded_call(*, prompt: str = "extract this graph") -> ReplayCall:
    return ReplayCall(
        order=0,
        input_digest=call_input_digest(
            order=0,
            prompt=prompt,
            system=None,
            temperature=0.0,
            json_mode=True,
            max_tokens=8192,
            generation_parameters=GENERATION_PARAMETERS,
            extractor_contract_version=1,
        ),
        raw_completion=RAW_COMPLETION,
    )


def _artifact() -> ReplayArtifact:
    return ReplayArtifact(
        schema_version=1,
        extractor_contract_version=1,
        created_at="2026-09-01T00:00:00+00:00",
        source_commit="abc1234",
        corpus_digest="a" * 64,
        extraction_model="google:gemini-2.5-flash",
        domain_digest="b" * 64,
        batch_size=2,
        generation_parameters=GENERATION_PARAMETERS,
        calls=[_recorded_call()],
        successful_batches=1,
        split_batches=0,
        failed_batches=0,
        entity_count=0,
        relationship_count=0,
        graph_digest="c" * 64,
    )


def test_candidate_is_content_addressed_and_never_overwritten(tmp_path: Path) -> None:
    artifact = _artifact()
    artifact_dir = tmp_path / "graph-replay"

    candidate = write_candidate(artifact, artifact_dir)

    assert candidate == artifact_dir / f"{artifact_sha256(artifact)}.json"
    original = candidate.read_bytes()
    with pytest.raises(GraphReplayError, match="already exists"):
        write_candidate(artifact, artifact_dir)
    assert candidate.read_bytes() == original


async def test_replay_rejects_call_drift_and_requires_exact_consumption() -> None:
    artifact = _artifact()
    replay = ReplayLLM(
        artifact.calls,
        extractor_contract_version=artifact.extractor_contract_version,
        generation_parameters=artifact.generation_parameters,
    )

    with pytest.raises(GraphReplayError, match="call 0"):
        await replay.generate_json("a changed prompt", max_tokens=8192)
    with pytest.raises(GraphReplayError, match="unused"):
        replay.assert_consumed()

    exact = ReplayLLM(
        artifact.calls,
        extractor_contract_version=artifact.extractor_contract_version,
        generation_parameters=artifact.generation_parameters,
    )
    assert await exact.generate_json("extract this graph", max_tokens=8192) == {
        "entities": [],
        "relationships": [],
    }
    exact.assert_consumed()
    with pytest.raises(GraphReplayError, match="missing recorded call"):
        await exact.generate_json("extract this graph", max_tokens=8192)


async def test_canonical_entities_do_not_inherit_database_order_for_equal_semantic_keys() -> None:
    """Casefold-equivalent rows use their complete ID-free payload as a tie-break."""

    class Result:
        def __init__(self, rows: list[Any]) -> None:
            self.rows = rows

        def all(self) -> list[Any]:
            return self.rows

        def scalars(self) -> Result:
            return self

    class Session:
        def __init__(self, entities: list[Any]) -> None:
            self.results = iter((Result([]), Result([]), Result(entities), Result([])))

        async def __aenter__(self) -> Session:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def execute(self, statement: object) -> Result:
            return next(self.results)

    first = SimpleNamespace(
        id="database-id-first",
        name="Straße",
        entity_type="Feedstock",
        description="zeta payload",
        aliases=["beta"],
        document_ids=[],
        chunk_ids=[],
    )
    second = SimpleNamespace(
        id="database-id-second",
        name="STRASSE",
        entity_type="Feedstock",
        description="alpha payload",
        aliases=["alpha"],
        document_ids=[],
        chunk_ids=[],
    )

    forward, _, _ = await _canonical_graph(lambda: Session([first, second]))  # type: ignore[arg-type]
    reversed_rows, _, _ = await _canonical_graph(  # type: ignore[arg-type]
        lambda: Session([second, first])
    )

    assert forward == reversed_rows
    assert "database-id" not in repr(forward)
