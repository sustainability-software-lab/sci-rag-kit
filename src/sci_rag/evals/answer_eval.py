"""End-to-end answer evaluation: generate, then grade.

For every seed question: run the full pipeline (retrieve + generate), then
grade the answer with the blind grounding pass, and, when the question has
an expert reference, the separate correctness pass. Per-question failures
are recorded, never fatal, so one flaky call cannot torch an hour-long run.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from sci_rag.answer import AnswerEngine
from sci_rag.answer.generator import format_sources
from sci_rag.evals.judge import (
    CorrectnessGrade,
    GroundingGrade,
    grade_correctness,
    grade_grounding,
)
from sci_rag.evals.seeds import SeedQuestion
from sci_rag.llm import LLMClient
from sci_rag.retrieve import RetrievalScope

log = structlog.get_logger(__name__)


@dataclass
class AnswerEvalRecord:
    question_id: str
    tags: list[str]
    answer_text: str = ""
    source_count: int = 0
    cited_count: int = 0
    degraded_stages: list[str] | None = None
    grounding: GroundingGrade | None = None
    correctness: CorrectnessGrade | None = None
    error: str | None = None


async def run_answer_eval(
    engine: AnswerEngine,
    judge_llm: LLMClient,
    questions: list[SeedQuestion],
    *,
    profile: str = "deep",
    limit: int = 8,
    scope: RetrievalScope | None = None,
) -> list[AnswerEvalRecord]:
    records: list[AnswerEvalRecord] = []
    for question in questions:
        record = AnswerEvalRecord(question_id=question.id, tags=question.tags)
        records.append(record)
        try:
            result = await engine.answer(
                question.question, profile=profile, limit=limit, scope=scope
            )
        except Exception as exc:
            record.error = f"answer failed: {type(exc).__name__}: {exc}"
            log.warning("answer_eval_generation_failed", question=question.id)
            continue
        record.answer_text = result.text
        record.source_count = len(result.sources)
        record.cited_count = len(result.cited_sources)
        record.degraded_stages = result.retrieval.degraded_stages

        try:
            record.grounding = await grade_grounding(
                judge_llm,
                engine.domain,
                question=question.question,
                answer_text=result.text,
                sources_block=format_sources(result.retrieval)
                if result.retrieval.items
                else "(no sources were retrieved)",
            )
        except Exception as exc:
            record.error = f"grounding judge failed: {type(exc).__name__}: {exc}"
            log.warning("answer_eval_grounding_failed", question=question.id)

        if question.reference_answer:
            try:
                record.correctness = await grade_correctness(
                    judge_llm,
                    engine.domain,
                    question=question.question,
                    reference_answer=question.reference_answer,
                    answer_text=result.text,
                )
            except Exception as exc:
                record.error = f"correctness judge failed: {type(exc).__name__}: {exc}"
                log.warning("answer_eval_correctness_failed", question=question.id)
    return records


def summarize_answer_records(records: list[AnswerEvalRecord]) -> dict[str, float]:
    groundings = [r.grounding for r in records if r.grounding is not None]
    correctnesses = [r.correctness for r in records if r.correctness is not None]
    summary: dict[str, float] = {
        "n": float(len(records)),
        "graded": float(len(groundings)),
        "failed": float(sum(1 for r in records if r.error)),
    }
    if groundings:
        summary["groundedness_mean"] = sum(g.groundedness for g in groundings) / len(groundings)
        summary["citation_accuracy_mean"] = sum(g.citation_accuracy for g in groundings) / len(
            groundings
        )
        summary["completeness_mean"] = sum(g.completeness for g in groundings) / len(groundings)
    if correctnesses:
        summary["correctness_mean"] = sum(c.correctness for c in correctnesses) / len(correctnesses)
    return summary
