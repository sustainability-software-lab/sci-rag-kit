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
            "records": [],
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
            config("with_rerank", 1.0),
            config("auto_routed", 0.89),
        ],
    }


def answers_fixture() -> dict:
    return {
        "kind": "answers",
        "git_commit": "abc1234",
        "snapshot": "v0.2-demo",
        "corpus": {"documents": 5, "chunks": 34},
        "summary": {"n": 10.0, "graded": 10.0, "failed": 0.0},
        "summary_ci": {
            "groundedness": {"mean": 2.0, "lo": 2.0, "hi": 2.0, "n": 10.0},
            "correctness": {"mean": 1.6, "lo": 1.1, "hi": 2.0, "n": 10.0},
        },
        "records": [],
    }


def test_renders_full_page(tmp_path: Path) -> None:
    retrieval = tmp_path / "retrieval.json"
    answers = tmp_path / "answers.json"
    retrieval.write_text(json.dumps(retrieval_fixture()))
    answers.write_text(json.dumps(answers_fixture()))
    page = render_benchmarks(retrieval, answers)
    assert "full_deep" in page and "with_rerank" in page and "auto_routed" in page
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
