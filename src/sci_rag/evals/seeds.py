"""Seed questions: the ground truth your evaluation runs against.

A seed question is something a domain expert can vouch for: the question,
what a correct answer must say, which documents contain it, and a few
distinctive phrases from the passages that answer it. Ten good questions
beat a hundred vague ones; grow the set as real users surprise you.

Questions tagged ``unanswerable`` are honesty probes: retrieval metrics
skip them, and the answer evaluation checks that the assistant admits the
gap instead of inventing something.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


class SeedQuestion(BaseModel):
    id: str
    question: str
    reference_answer: str | None = None
    reference_titles: list[str] = Field(default_factory=list)
    evidence_phrases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @property
    def answerable(self) -> bool:
        return "unanswerable" not in self.tags


def load_seed_questions(path: Path) -> list[SeedQuestion]:
    if not path.exists():
        raise FileNotFoundError(
            f"No seed questions at {path}. Write ground-truth questions there "
            "(see domain/eval_seed_questions.jsonl for the format)."
        )
    questions: list[SeedQuestion] = []
    seen_ids: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name} line {line_number} is not valid JSON: {exc}") from exc
        question = SeedQuestion.model_validate(data)
        if question.id in seen_ids:
            raise ValueError(
                f"{path.name} line {line_number}: duplicate question id {question.id!r}"
            )
        seen_ids.add(question.id)
        questions.append(question)
    return questions
