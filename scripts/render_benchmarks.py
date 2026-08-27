"""Render docs/benchmarks.md from eval report JSONs.

Usage (what `make benchmark` runs after the eval passes):

    uv run python scripts/render_benchmarks.py \
        --retrieval eval_results/<run>-retrieval-ablation/report.json \
        --answers eval_results/<run>-answers/report.json \
        --output docs/benchmarks.md

The page states exactly what was measured (corpus fingerprint, snapshot
name, git commit, model ids), shows every ablation row with its 95%
bootstrap CI, and says plainly what the numbers do and do not support.
No number appears here that was not computed by the eval harness.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

METRICS = ("hit_at_5", "hit_at_10", "mrr", "ndcg_at_10")
METRIC_LABELS = {"hit_at_5": "hit@5", "hit_at_10": "hit@10", "mrr": "MRR", "ndcg_at_10": "nDCG@10"}


def _ci_cell(ci: dict[str, float] | None) -> str:
    if not ci:
        return "-"
    return f"{ci['mean']:.2f} [{ci['lo']:.2f}, {ci['hi']:.2f}]"


def _load(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    if path.is_dir():
        path = path / "report.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _calibration_for(answers_path: Path | None) -> dict[str, Any] | None:
    if answers_path is None:
        return None
    directory = answers_path if answers_path.is_dir() else answers_path.parent
    calibration = directory / "calibration.json"
    if calibration.exists():
        return json.loads(calibration.read_text(encoding="utf-8"))
    return None


def render_benchmarks(retrieval_path: Path, answers_path: Path | None) -> str:
    retrieval = _load(retrieval_path)
    assert retrieval is not None
    answers = _load(answers_path)
    calibration = _calibration_for(answers_path)
    corpus = retrieval.get("corpus", {})
    snapshot = retrieval.get("snapshot")
    commit = retrieval.get("git_commit", "unknown")
    versions = ", ".join(corpus.get("embedding_versions", [])) or "unknown"

    try:
        from sci_rag.config import get_settings

        llm_model = get_settings().llm_model
    except Exception:
        llm_model = "unknown"

    lines = [
        "# Benchmarks",
        "",
        "Measured results on the shipped demo corpus, regenerated with one",
        "command. This page exists to prove the evaluation harness end to",
        "end and to publish honest numbers for THIS template on ITS demo",
        "corpus; it makes no state-of-the-art claim and does not compare",
        "against other systems (see docs/choosing-sci-rag-kit.md for the",
        "honest comparison on axes other than benchmark scores).",
        "",
        "## What was measured",
        "",
        f"- Corpus: {corpus.get('documents')} documents, {corpus.get('chunks')} chunks, "
        f"{corpus.get('entities')} entities, {corpus.get('relationships')} relationships, "
        f"{corpus.get('communities')} communities (the synthetic agricultural-residue "
        "demo corpus shipped in `data/demo/`)",
        f"- Corpus snapshot: `{snapshot or 'not recorded'}` "
        "(see `data/snapshots/`; the digest pins the exact document set)",
        f"- Embedding: `{versions}`; generation and judging: `{llm_model}`",
        f"- Code: commit `{commit}`",
        f"- Rendered: {datetime.now(UTC).strftime('%Y-%m-%d')}",
        "",
        "## Retrieval ablations",
        "",
        "Cells are mean [95% bootstrap CI], resampled per question. The",
        "demo corpus has single-digit questions, so intervals are wide by",
        "construction: treat differences whose intervals overlap heavily as",
        "noise, and read the table for the qualitative story (which layers",
        "earn their keep) rather than decimal places. On a small sample",
        "like this, that qualitative story is the only defensible claim.",
        "",
        "| Config | " + " | ".join(METRIC_LABELS[m] for m in METRICS) + " | n |",
        "|--------|" + "---:|" * len(METRICS) + "---:|",
    ]
    for config in retrieval.get("configs", []):
        ci = config.get("metrics_ci", {})
        n = int(ci.get("n", config.get("metrics", {}).get("n", 0)))
        cells = " | ".join(_ci_cell(ci.get(metric)) for metric in METRICS)
        lines.append(f"| {config['name']} | {cells} | {n} |")

    lines += [
        "",
        "How to read it:",
        "",
        "- `full_deep` vs the `*_only` rows shows what fusion buys over any",
        "  single layer.",
        "- `no_graph` / `no_hyde` / `no_community` vs `full_deep` shows each",
        "  layer's marginal contribution on this corpus.",
        "- `with_rerank` vs `no_rerank` is the paired evidence the reranker",
        "  must show before `retrieval.reranker.enabled: true` is justified.",
        "- `auto_routed` vs `full_deep` and `interactive` is the evidence for",
        "  (or against) making adaptive routing a default. Until it clearly",
        "  matches `full_deep` at lower cost, `auto` stays opt-in.",
        "",
    ]

    if answers is not None:
        summary_ci = answers.get("summary_ci", {})
        summary = answers.get("summary", {})
        lines += [
            "## Judged answers (blind two-pass judge)",
            "",
            "| Dimension | Mean [95% CI] |",
            "|-----------|--------------:|",
        ]
        for dimension in ("groundedness", "citation_accuracy", "completeness", "correctness"):
            if dimension in summary_ci:
                lines.append(f"| {dimension} | {_ci_cell(summary_ci[dimension])} |")
        lines += [
            f"| graded / total | {int(summary.get('graded', 0))} / {int(summary.get('n', 0))} |",
            "",
            "The grounding judge never sees the reference answer; correctness",
            "is graded in a separate reference-only pass (docs/evaluation.md).",
            "",
        ]

    if calibration is not None:
        lines += [
            "## Judge calibration (human labels vs judge)",
            "",
            "Cohen's kappa between independent human labels",
            "(`domain/eval_calibration_labels.jsonl`, a NON-EXPERT seed set)",
            "and the judge's scores on the same answers:",
            "",
            "| Dimension | kappa | exact agreement | n |",
            "|-----------|------:|----------------:|--:|",
        ]
        for name, d in calibration.get("dimensions", {}).items():
            lines.append(f"| {name} | {d['kappa']:.2f} | {d['exact_agreement']:.2f} | {d['n']} |")
        lines += [
            "",
            "Kappa is reported as measured, never asserted as a target. A",
            "kappa of 0 with high exact agreement means one rater was",
            "constant (kappa cannot credit agreement it attributes to",
            "chance); the fix is a seed set with more score variance, not a",
            "different formula. Expert labels supersede this seed set.",
            "",
        ]

    lines += [
        "## Reproduce it",
        "",
        "```bash",
        "make benchmark",
        "```",
        "",
        "Prerequisites: Docker (for the pgvector Postgres), uv, and Google",
        "credentials in `.env` (`SCI_RAG_GOOGLE_API_KEY` or",
        "`SCI_RAG_GCP_PROJECT`; see `.env.example`). The target ingests the",
        "demo corpus with real embeddings, builds the graph, snapshots the",
        "corpus, runs the full retrieval ablation plus the judged answers",
        "eval, and re-renders this page from the report JSONs. Without",
        "credentials the eval commands stop with a clear message; nothing",
        "on this page is reachable offline, by design: published numbers",
        "come from real models or not at all.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retrieval", type=Path, required=True)
    parser.add_argument("--answers", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=Path("docs/benchmarks.md"))
    args = parser.parse_args()
    page = render_benchmarks(args.retrieval, args.answers)
    args.output.write_text(page, encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
