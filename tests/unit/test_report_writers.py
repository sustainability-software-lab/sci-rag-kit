"""Eval report artifacts: payload shape and human-readable rendering."""

from __future__ import annotations

import json
from pathlib import Path

from sci_rag.evals.answer_eval import AnswerEvalRecord
from sci_rag.evals.judge import CorrectnessGrade, GroundingGrade
from sci_rag.evals.report import (
    answers_markdown,
    answers_payload,
    retrieval_markdown,
    retrieval_payload,
    write_report,
)
from sci_rag.evals.retrieval_eval import (
    AblationConfig,
    QuestionRetrievalRecord,
    RetrievalEvalResult,
)

FINGERPRINT = {
    "documents": 5,
    "chunks": 34,
    "entities": 95,
    "relationships": 99,
    "communities": 9,
    "latest_ingested_at": "2026-08-26T00:00:00+00:00",
    "embedding_versions": ["local-hash-v1@64"],
}


def _retrieval_results() -> list[RetrievalEvalResult]:
    return [
        RetrievalEvalResult(
            AblationConfig("full_deep", "everything"),
            [
                QuestionRetrievalRecord("hit-first", 1, True, True, 10, []),
                QuestionRetrievalRecord("missed", None, False, False, 10, ["hyde"]),
            ],
        )
    ]


def test_retrieval_report_roundtrip(tmp_path: Path) -> None:
    results = _retrieval_results()
    payload = retrieval_payload(results, FINGERPRINT)
    markdown = retrieval_markdown(results, FINGERPRINT)

    assert payload["corpus"]["documents"] == 5
    assert payload["configs"][0]["metrics"]["hit_at_5"] == 0.5
    assert "| full_deep | 0.50 " in markdown
    assert "[" in markdown and "]" in markdown, "expected 95% CI brackets in the table"
    assert "small sample" in markdown, "expected a small-n warning for n=2"
    assert "## Missed questions" in markdown and "missed" in markdown

    json_path, md_path = write_report(
        kind="retrieval", payload=payload, markdown=markdown, base_dir=tmp_path
    )
    assert json.loads(json_path.read_text())["kind"] == "retrieval"
    assert md_path.read_text().startswith("# Retrieval evaluation")


def test_answers_report_renders_grades_and_errors(tmp_path: Path) -> None:
    records = [
        AnswerEvalRecord(
            question_id="good",
            tags=[],
            answer_text="fine [1]",
            source_count=3,
            cited_count=1,
            grounding=GroundingGrade(2, 2, 1, "solid"),
            correctness=CorrectnessGrade(2, "matches"),
        ),
        AnswerEvalRecord(
            question_id="probe",
            tags=["unanswerable"],
            answer_text="not covered",
            grounding=GroundingGrade(2, 2, 2, "honest"),
        ),
        AnswerEvalRecord(question_id="broken", tags=[], error="answer failed: boom"),
    ]
    payload = answers_payload(records, FINGERPRINT)
    markdown = answers_markdown(records, FINGERPRINT)

    summary = payload["summary"]
    assert summary["n"] == 3.0 and summary["graded"] == 2.0 and summary["failed"] == 1.0
    assert summary["groundedness_mean"] == 2.0
    assert summary["correctness_mean"] == 2.0
    assert "honesty probe" in markdown
    assert "answer failed: boom" in markdown
    assert "| good | 2 | 2 | 1 | 2 |" in markdown
