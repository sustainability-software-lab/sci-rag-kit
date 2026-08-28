"""The benchmark page renderer: report JSONs in, honest markdown out."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from scripts.render_benchmarks import render_benchmarks


def retrieval_fixture() -> dict:
    def config(name: str, hit5: float) -> dict:
        return {
            "name": name,
            "description": f"{name} description",
            "metrics": {
                "n": 9.0,
                "hit_at_5": hit5,
                "hit_at_10": hit5,
                "mrr": hit5,
                "ndcg_at_10": hit5,
            },
            "metrics_ci": {
                "n": 9,
                "hit_at_5": {"mean": hit5, "lo": hit5 - 0.1, "hi": 1.0, "n": 9.0},
                "hit_at_10": {"mean": hit5, "lo": hit5 - 0.1, "hi": 1.0, "n": 9.0},
                "mrr": {"mean": hit5, "lo": hit5 - 0.15, "hi": 1.0, "n": 9.0},
                "ndcg_at_10": {"mean": hit5, "lo": hit5 - 0.12, "hi": 1.0, "n": 9.0},
            },
            "records": [
                {"question_id": "q1", "first_relevant_rank": 1, "relevant_ranks": [1]},
                {"question_id": "q2", "first_relevant_rank": 2, "relevant_ranks": [2]},
            ],
        }

    return {
        "kind": "retrieval",
        "generated_at": "2026-08-27T16:00:00+00:00",
        "git_commit": "abc1234",
        "snapshot": "v0.2-demo",
        "corpus": {
            "documents": 5,
            "chunks": 34,
            "entities": 76,
            "relationships": 72,
            "communities": 10,
            "embedding_versions": ["gemini-embedding-001@1536"],
        },
        "configs": [
            config("full_deep", 1.0),
            config("keyword_only", 0.33),
            config("confidence_weighted", 1.0),
            config("with_citations", 1.0),
            config("no_retracted", 1.0),
            config("with_rerank", 1.0),
            config("auto_routed", 0.89),
        ],
    }


def answers_fixture(*, compressed: bool = False) -> dict:
    after = [300, 500] if compressed else [900, 1100]
    return {
        "kind": "answers",
        "git_commit": "abc1234",
        "snapshot": "v0.2-demo",
        "corpus": {"documents": 5, "chunks": 34},
        "models": {
            "answer": "google:gemini-2.5-flash",
            "judge": "anthropic:claude-haiku-4-5",
        },
        "config": {"compression": compressed},
        "summary": {
            "n": 2.0,
            "graded": 2.0,
            "failed": 0.0,
            "prompt_tokens_before_median": 1000.0,
            "prompt_tokens_after_median": 400.0 if compressed else 1000.0,
        },
        "summary_ci": {
            "groundedness": {"mean": 2.0, "lo": 2.0, "hi": 2.0, "n": 2.0},
            "correctness": {"mean": 1.5, "lo": 1.0, "hi": 2.0, "n": 2.0},
        },
        "records": [
            {
                "question_id": f"q{index}",
                "grounding": {
                    "groundedness": 2,
                    "citation_accuracy": 2,
                    "completeness": 2,
                },
                "correctness": {"correctness": score},
                "prompt_tokens_after": after[index - 1],
            }
            for index, score in ((1, 1), (2, 2))
        ],
    }


def resolved_entities_fixture() -> dict:
    fixture = retrieval_fixture()
    fixture["kind"] = "retrieval-condition"
    fixture["snapshot"] = "v0.2-demo-resolved"
    fixture["corpus"] = {**fixture["corpus"], "entities": 75}
    fixture["configs"] = [
        {
            **fixture["configs"][0],
            "name": "resolved_entities",
            "description": "audited post-resolution condition",
        }
    ]
    return fixture


def resolution_baseline_fixture() -> dict:
    fixture = retrieval_fixture()
    fixture["snapshot"] = "v0.2-demo-resolution-control"
    fixture["corpus"] = {**fixture["corpus"], "entities": 77}
    fixture["configs"] = [fixture["configs"][0]]
    return fixture


def test_renders_full_page(tmp_path: Path) -> None:
    retrieval = tmp_path / "retrieval.json"
    answers = tmp_path / "answers.json"
    compressed_answers = tmp_path / "compressed-answers.json"
    resolution_baseline = tmp_path / "resolution-baseline.json"
    resolved_entities = tmp_path / "resolved-entities.json"
    retrieval.write_text(json.dumps(retrieval_fixture()))
    answers.write_text(json.dumps(answers_fixture()))
    compressed_answers.write_text(json.dumps(answers_fixture(compressed=True)))
    resolution_baseline.write_text(json.dumps(resolution_baseline_fixture()))
    resolved_entities.write_text(json.dumps(resolved_entities_fixture()))
    page = render_benchmarks(
        retrieval,
        answers,
        compressed_answers_path=compressed_answers,
        resolution_baseline_path=resolution_baseline,
        resolved_entities_path=resolved_entities,
    )
    assert "full_deep" in page and "with_rerank" in page and "auto_routed" in page
    assert "confidence_weighted" in page and "with_citations" in page and "no_retracted" in page
    assert "zero document edges" in page
    assert "Entity-resolution condition" in page and "resolved_entities" in page
    assert "neither a retrieval gain nor a degradation" in page
    assert "Snippet-compression condition" in page and "prompt_tokens" in page
    assert "google:gemini-2.5-flash" in page and "anthropic:claude-haiku-4-5" in page
    assert "fresh" in page and "isolated Postgres database" in page
    assert "1.00 [0.90, 1.00]" in page  # CI formatting
    assert "v0.2-demo" in page  # snapshot name
    assert "abc1234" in page  # commit
    assert "gemini-embedding-001@1536" in page
    assert "make benchmark" in page  # reproduction command
    assert "groundedness" in page  # answers table present
    assert "small" in page.lower()  # small-sample honesty


def test_renders_without_answers(tmp_path: Path) -> None:
    retrieval = tmp_path / "retrieval.json"
    retrieval.write_text(json.dumps(retrieval_fixture()))
    page = render_benchmarks(retrieval, None)
    assert "full_deep" in page
    assert "groundedness" not in page


def test_includes_calibration_when_present(tmp_path: Path) -> None:
    retrieval = tmp_path / "retrieval.json"
    answers_dir = tmp_path / "answers-run"
    answers_dir.mkdir()
    answers = answers_dir / "report.json"
    retrieval.write_text(json.dumps(retrieval_fixture()))
    answers.write_text(json.dumps(answers_fixture()))
    (answers_dir / "calibration.json").write_text(
        json.dumps(
            {
                "matched_n": 10,
                "unmatched_label_ids": [],
                "dimensions": {
                    "groundedness": {
                        "kappa": 1.0,
                        "n": 10,
                        "exact_agreement": 1.0,
                        "band": "almost perfect",
                        "matrix": [[0, 0, 0], [0, 0, 0], [0, 0, 10]],
                    }
                },
            }
        )
    )
    page = render_benchmarks(retrieval, answers)
    assert "kappa" in page.lower()
    assert "1.00" in page
