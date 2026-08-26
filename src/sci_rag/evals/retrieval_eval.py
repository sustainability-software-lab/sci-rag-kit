"""Retrieval evaluation: does the right evidence come back, and which
layers earn their keep?

Relevance is judged at the evidence level, mechanically and transparently:
a retrieved item counts as relevant to a question if it comes from one of
the question's reference documents, or its text contains one of the
question's distinctive evidence phrases (whitespace- and case-normalized).
That is a deliberate, honest granularity for retrieval; grading the
quality of generated ANSWERS is the blind judge's job, never substring
matching.

The ablation configs re-run the same questions with layers switched off,
which is the only honest way to know what the graph, HyDE, or community
layers actually contribute on YOUR corpus before touching any fusion
weight.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sci_rag.evals.seeds import SeedQuestion
from sci_rag.retrieve import RetrievalScope, RetrievedItem, Retriever


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def is_relevant(item: RetrievedItem, question: SeedQuestion) -> bool:
    if item.title and any(
        _normalize(item.title) == _normalize(title) for title in question.reference_titles
    ):
        return True
    content = _normalize(item.content)
    return any(
        len(phrase.strip()) >= 3 and _normalize(phrase) in content
        for phrase in question.evidence_phrases
    )


@dataclass
class AblationConfig:
    name: str
    description: str
    kwargs: dict[str, Any] = field(default_factory=dict)


DEFAULT_ABLATIONS: list[AblationConfig] = [
    AblationConfig("full_deep", "All five layers (deep profile)", {"profile": "deep"}),
    AblationConfig(
        "interactive",
        "Vector + keyword only, as interactive callers see it",
        {"profile": "interactive"},
    ),
    AblationConfig(
        "vector_only",
        "Dense vectors alone",
        {
            "profile": "deep",
            "include_keyword": False,
            "include_graph": False,
            "include_community": False,
            "include_hyde": False,
        },
    ),
    AblationConfig(
        "keyword_only",
        "Full-text search alone",
        {
            "profile": "deep",
            "include_vector": False,
            "include_graph": False,
            "include_community": False,
            "include_hyde": False,
        },
    ),
    AblationConfig(
        "no_graph", "Deep without graph traversal", {"profile": "deep", "include_graph": False}
    ),
    AblationConfig("no_hyde", "Deep without HyDE", {"profile": "deep", "include_hyde": False}),
    AblationConfig(
        "no_community",
        "Deep without community summaries",
        {"profile": "deep", "include_community": False},
    ),
]


@dataclass
class QuestionRetrievalRecord:
    question_id: str
    first_relevant_rank: int | None
    hit_at_5: bool
    hit_at_10: bool
    retrieved: int
    degraded_stages: list[str]


@dataclass
class RetrievalEvalResult:
    config: AblationConfig
    records: list[QuestionRetrievalRecord]

    @property
    def metrics(self) -> dict[str, float]:
        n = len(self.records)
        if n == 0:
            return {"n": 0.0, "hit_at_5": 0.0, "hit_at_10": 0.0, "mrr": 0.0}
        return {
            "n": float(n),
            "hit_at_5": sum(r.hit_at_5 for r in self.records) / n,
            "hit_at_10": sum(r.hit_at_10 for r in self.records) / n,
            "mrr": sum(1.0 / r.first_relevant_rank for r in self.records if r.first_relevant_rank)
            / n,
        }


async def run_retrieval_eval(
    retriever: Retriever,
    questions: list[SeedQuestion],
    *,
    configs: list[AblationConfig] | None = None,
    limit: int = 10,
    scope: RetrievalScope | None = None,
) -> list[RetrievalEvalResult]:
    configs = configs or [DEFAULT_ABLATIONS[0]]
    answerable = [q for q in questions if q.answerable]
    results: list[RetrievalEvalResult] = []
    for config in configs:
        records: list[QuestionRetrievalRecord] = []
        for question in answerable:
            result = await retriever.retrieve(
                question.question, limit=limit, scope=scope, **config.kwargs
            )
            first_rank: int | None = None
            for rank, item in enumerate(result.items, start=1):
                if is_relevant(item, question):
                    first_rank = rank
                    break
            records.append(
                QuestionRetrievalRecord(
                    question_id=question.id,
                    first_relevant_rank=first_rank,
                    hit_at_5=first_rank is not None and first_rank <= 5,
                    hit_at_10=first_rank is not None and first_rank <= 10,
                    retrieved=len(result.items),
                    degraded_stages=result.degraded_stages,
                )
            )
        results.append(RetrievalEvalResult(config=config, records=records))
    return results
