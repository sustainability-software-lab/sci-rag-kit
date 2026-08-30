"""What a published benchmark number has to carry with it.

A clean reproduction of `make benchmark` from the committed commit produced a
materially different page: same five documents and 34 chunks, but 93 entities
against the committed 83, 106 relationships against 79, 12 communities against
7, and mean correctness 1.9 against 1.3. The route completed and exited 0, and
the page was rewritten in place, so the only visible evidence that anything had
moved was the diff nobody was asked to read.

Two separate problems live in that. The first is that the report did not record
enough to tell expected model variance apart from a changed input: the
retrieval report named no model at all, and the renderer printed whichever
model its own environment happened to have, not the one that produced the
numbers. The second is that a re-render silently replaced published values.

These guards cover the receipt and the refusals. The comparison itself is in
`test_benchmark_comparison.py`.
"""

from __future__ import annotations

import json
from pathlib import Path
from runpy import run_path
from typing import Any

import pytest

from sci_rag.evals.report import PROVENANCE_FIELDS, provenance_block, retrieval_payload

# The renderers are scripts rather than package modules, so they are loaded
# the way `test_doc_renderers.py` loads them.
_MODULE: dict | None = None


def _renderer() -> dict:  # type: ignore[type-arg]
    global _MODULE
    if _MODULE is None:
        _MODULE = run_path("scripts/render_benchmarks.py")
    return _MODULE


ROOT = Path(__file__).resolve().parents[2]


def test_a_receipt_names_every_input_that_can_move_a_number() -> None:
    """Counts are outcomes. These are the inputs that produce them."""
    assert set(PROVENANCE_FIELDS) == {
        "embedding",
        "models",
        "domain_digest",
        "decoding",
    }


def test_provenance_records_the_effective_models_and_not_the_defaults() -> None:
    from sci_rag.config import Settings

    settings = Settings(
        _env_file=None,
        llm_model="gemini-2.5-flash",
        extraction_model="anthropic:claude-haiku-4-5",
        judge_model="openai-compatible:some/judge",
        embedding_model="gemini-embedding-001",
        embedding_dim=1536,
    )

    block = provenance_block(settings, domain_dir=ROOT / "domain")

    assert block["models"]["answer"] == "google:gemini-2.5-flash"
    assert block["models"]["extraction"] == "anthropic:claude-haiku-4-5"
    assert block["models"]["judge"] == "openai-compatible:some/judge"
    assert block["embedding"] == "gemini-embedding-001@1536"
    # Decoding is what makes a run repeatable at all, so it is on the receipt.
    assert "temperature" in block["decoding"]


def test_the_domain_digest_moves_when_the_ontology_or_a_prompt_moves(tmp_path: Path) -> None:
    """A prompt edit changes every extracted entity and no count records it."""
    from sci_rag.config import Settings

    domain = tmp_path / "domain"
    (domain / "prompts").mkdir(parents=True)
    (domain / "domain.yaml").write_text("name: a\n", encoding="utf-8")
    (domain / "prompts" / "entity_extraction.md").write_text("find things\n", encoding="utf-8")

    settings = Settings(_env_file=None)
    before = provenance_block(settings, domain_dir=domain)["domain_digest"]

    (domain / "prompts" / "entity_extraction.md").write_text(
        "find OTHER things\n", encoding="utf-8"
    )
    after = provenance_block(settings, domain_dir=domain)["domain_digest"]

    assert before != after


def test_a_retrieval_report_carries_the_receipt() -> None:
    """The retrieval ablation runs graph and HyDE, so it depends on a model."""
    payload = retrieval_payload([], {"documents": 5}, provenance={"models": {}})

    assert "provenance" in payload


# --- the renderer refuses an unusable receipt -------------------------------


def _report(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": "retrieval",
        "git_commit": "abc1234",
        "snapshot": "benchmark-20260830-000000",
        "corpus": {"documents": 5, "chunks": 34, "embedding_versions": ["local-hash-v1@64"]},
        "provenance": {
            "embedding": "local-hash-v1@64",
            "models": {"answer": "google:gemini-2.5-flash"},
            "domain_digest": "0" * 64,
            "decoding": {"temperature": 0.0},
        },
        "configs": [],
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize("field", ["provenance", "git_commit", "snapshot"])
def test_the_renderer_refuses_a_report_missing_a_required_field(tmp_path: Path, field: str) -> None:
    ProvenanceError = _renderer()["ProvenanceError"]
    render_benchmarks = _renderer()["render_benchmarks"]

    report = _report()
    report.pop(field)
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ProvenanceError) as caught:
        render_benchmarks(path, None)

    assert field in str(caught.value)


def test_the_renderer_refuses_reports_that_disagree_about_their_inputs(tmp_path: Path) -> None:
    """Two halves of one page have to come from one run.

    A retrieval report from one commit and an answers report from another
    render into a single page that describes neither.
    """
    ProvenanceError = _renderer()["ProvenanceError"]
    render_benchmarks = _renderer()["render_benchmarks"]

    retrieval = tmp_path / "retrieval.json"
    retrieval.write_text(json.dumps(_report()), encoding="utf-8")
    answers = tmp_path / "answers.json"
    answers.write_text(
        json.dumps(
            _report(
                kind="answers",
                git_commit="def5678",
                config={"compression": False},
                summary={},
                records=[],
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(ProvenanceError) as caught:
        render_benchmarks(retrieval, answers)

    assert "git_commit" in str(caught.value)


def test_the_page_names_the_models_the_run_used_not_the_ambient_ones(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The renderer used to print `get_settings().llm_model` from its own shell."""
    render_benchmarks = _renderer()["render_benchmarks"]

    monkeypatch.setenv("SCI_RAG_LLM_MODEL", "not-the-model-that-ran")
    path = tmp_path / "report.json"
    path.write_text(json.dumps(_report()), encoding="utf-8")

    page = render_benchmarks(path, None)

    assert "google:gemini-2.5-flash" in page
    assert "not-the-model-that-ran" not in page
