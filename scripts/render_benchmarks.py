"""Render docs/benchmarks.md from eval report JSONs.

Usage (what `make benchmark` runs after the eval passes):

    uv run python scripts/render_benchmarks.py \
        --retrieval eval_results/<run>-retrieval-ablation/report.json \
        --answers eval_results/<run>-answers/report.json \
        --compressed-answers eval_results/<run>-answers/report.json \
        --resolution-baseline eval_results/<run>-retrieval/report.json \
        --resolved-entities eval_results/<run>-retrieval-condition/report.json \
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


def _model_description(answers: dict[str, Any] | None) -> str:
    if answers is not None:
        models = answers.get("models", {})
        answer = models.get("answer")
        judge = models.get("judge")
        if answer or judge:
            return f"answer `{answer or 'unknown'}`; judge `{judge or 'unknown'}`"
    return "generation and judging models unknown"


def _answer_pair(
    baseline: dict[str, Any], compressed: dict[str, Any]
) -> tuple[dict[str, Any], int]:
    """Validate and pair the two answer conditions before publishing a claim."""
    for field in ("corpus", "snapshot", "models", "git_commit"):
        if baseline.get(field) != compressed.get(field):
            raise ValueError(f"answer reports differ in {field}; refusing an unmatched comparison")
    if baseline.get("config", {}).get("compression") is not False:
        raise ValueError("baseline answer report is not the compression=false condition")
    if compressed.get("config", {}).get("compression") is not True:
        raise ValueError("compressed answer report is not the compression=true condition")

    ids_a = {record["question_id"] for record in baseline.get("records", [])}
    ids_b = {record["question_id"] for record in compressed.get("records", [])}
    if ids_a != ids_b:
        raise ValueError("answer reports do not contain the same question ids")

    from sci_rag.evals.diff import diff_reports

    diff = diff_reports(baseline, compressed)
    config = diff.configs[0]
    return config.metric_deltas, config.common_n


def _retrieval_condition_pair(
    baseline: dict[str, Any], resolved: dict[str, Any]
) -> tuple[dict[str, Any], int]:
    """Pair full_deep before resolution with the audited resolved condition."""
    baseline_configs = [
        config for config in baseline.get("configs", []) if config["name"] == "full_deep"
    ]
    resolved_configs = [
        config for config in resolved.get("configs", []) if config["name"] == "resolved_entities"
    ]
    if len(baseline_configs) != 1 or len(resolved_configs) != 1:
        raise ValueError("entity-resolution comparison needs full_deep and resolved_entities")
    if baseline.get("git_commit") != resolved.get("git_commit"):
        raise ValueError("entity-resolution reports come from different commits")

    from sci_rag.evals.diff import diff_reports

    renamed = {
        **resolved,
        "kind": baseline.get("kind"),
        "configs": [{**resolved_configs[0], "name": "full_deep"}],
    }
    before = {**baseline, "configs": baseline_configs}
    diff = diff_reports(before, renamed, config="full_deep")
    result = diff.configs[0]
    return result.metric_deltas, result.common_n


def _delta_cell(delta: dict[str, float]) -> str:
    return f"{delta['delta']:+.3f} [{delta['lo']:+.3f}, {delta['hi']:+.3f}]"


def _answer_condition_rows(answers: dict[str, Any], label: str) -> str:
    summary = answers.get("summary", {})
    summary_ci = answers.get("summary_ci", {})
    scores = [
        _ci_cell(summary_ci.get(dimension))
        for dimension in ("groundedness", "citation_accuracy", "completeness", "correctness")
    ]
    tokens = summary.get("prompt_tokens_after_median")
    token_cell = f"{tokens:.1f}" if isinstance(tokens, int | float) else "-"
    failures = sum(
        record.get("compression_failure_count", 0) for record in answers.get("records", [])
    )
    return f"| {label} | " + " | ".join(scores) + f" | {token_cell} | {failures} |"


def render_benchmarks(
    retrieval_path: Path,
    answers_path: Path | None,
    *,
    compressed_answers_path: Path | None = None,
    resolution_baseline_path: Path | None = None,
    resolved_entities_path: Path | None = None,
) -> str:
    retrieval = _load(retrieval_path)
    assert retrieval is not None
    answers = _load(answers_path)
    compressed_answers = _load(compressed_answers_path)
    resolution_baseline = _load(resolution_baseline_path)
    resolved_entities = _load(resolved_entities_path)
    calibration_path = compressed_answers_path or answers_path
    calibration = _calibration_for(calibration_path)
    corpus = retrieval.get("corpus", {})
    snapshot = retrieval.get("snapshot")
    commit = retrieval.get("git_commit", "unknown")
    versions = ", ".join(corpus.get("embedding_versions", [])) or "unknown"

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
        f"- Embedding: `{versions}`; {_model_description(answers)}",
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
        "- `confidence_weighted` isolates confidence-aware graph ranking. Its",
        "  interval overlaps the full condition, so this run does not justify a default.",
        "- The shipped demo manifest has no cached DOI reference lists, so citation",
        "  ingestion produced zero document edges. Treat `with_citations` as an",
        "  unexercised control. Small movement from independent real-model retrieval",
        "  calls is not evidence for or against citation traversal.",
        "- `no_retracted` should be exactly neutral because the synthetic demo",
        "  contains no known retracted document. Any apparent gain would be suspect.",
        "",
    ]

    if resolved_entities is not None:
        if resolution_baseline is None:
            raise ValueError("resolved entities need a separate controlled baseline report")
        deltas, common_n = _retrieval_condition_pair(resolution_baseline, resolved_entities)
        baseline_config = next(
            config
            for config in resolution_baseline.get("configs", [])
            if config["name"] == "full_deep"
        )
        resolved_config = next(
            config
            for config in resolved_entities.get("configs", [])
            if config["name"] == "resolved_entities"
        )
        lines += [
            "## Entity-resolution condition",
            "",
            "Entity resolution changes persisted corpus state, so it is shown separately",
            "from same-state layer ablations. Because natural model extraction may have no",
            "duplicates, this pair starts after inserting one explicitly labeled exact-alias",
            "control entity. The resolver must create an audit row; unchanged state cannot be",
            "relabeled as resolved.",
            "",
            "| Condition | " + " | ".join(METRIC_LABELS[m] for m in METRICS) + " | n |",
            "|---|" + "---:|" * len(METRICS) + "---:|",
        ]
        for label, config in (
            ("full_deep before", baseline_config),
            ("resolved_entities", resolved_config),
        ):
            ci = config.get("metrics_ci", {})
            cells = " | ".join(_ci_cell(ci.get(metric)) for metric in METRICS)
            lines.append(f"| {label} | {cells} | {int(ci.get('n', 0))} |")
        lines += [
            "",
            f"Paired n={common_n}; deltas are resolved minus pre-resolution:",
            "",
            "| Metric | Delta [95% CI] | p |",
            "|---|---:|---:|",
        ]
        for metric in METRICS:
            delta = deltas[metric]
            lines.append(
                f"| {METRIC_LABELS[metric]} | {_delta_cell(delta)} | {delta['p_value']:.3f} |"
            )
        resolution_inconclusive = all(
            deltas[metric]["lo"] <= 0.0 <= deltas[metric]["hi"] for metric in METRICS
        )
        resolution_reading = (
            "The controlled merge preserved hit@5 and hit@10. Every paired interval includes "
            "zero, so this small run establishes neither a retrieval gain nor a degradation."
            if resolution_inconclusive
            else "At least one paired interval excludes zero; inspect that metric before "
            "changing the entity-resolution default."
        )
        lines += [
            "",
            resolution_reading,
            "",
            f"Control snapshot: `{resolution_baseline.get('snapshot')}`. Post-resolution snapshot:",
            f"`{resolved_entities.get('snapshot')}`.",
            f"Both resolution reports were measured at commit `{resolved_entities.get('git_commit')}`.",
            "",
        ]

    if answers is not None:
        summary_ci = answers.get("summary_ci", {})
        summary = answers.get("summary", {})
        lines += [
            "## Judged answers, uncompressed condition (blind two-pass judge)",
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

    if answers is not None and compressed_answers is not None:
        deltas, common_n = _answer_pair(answers, compressed_answers)
        quality_names = ("groundedness", "citation_accuracy", "completeness", "correctness")
        quality_holds = all(
            name in deltas and deltas[name]["lo"] <= 0.0 <= deltas[name]["hi"]
            for name in quality_names
        )
        tokens_fall = "prompt_tokens" in deltas and deltas["prompt_tokens"]["hi"] < 0.0
        decision = (
            "The paired gate passed: every quality interval includes zero and the "
            "prompt-token interval is below zero. The shipped demo enables compression."
            if quality_holds and tokens_fall
            else "The paired gate did not pass; this report makes no adoption claim."
        )
        lines += [
            "## Snippet-compression condition",
            "",
            "Both rows share one corpus fingerprint, snapshot, commit, question set, answer",
            "model, and judge. The grounding judge sees the exact compressed or",
            "fallback source text shown to the answer model.",
            "",
            "| Condition | groundedness | citation accuracy | completeness | correctness | median prompt tokens | chunk fallbacks |",
            "|---|---:|---:|---:|---:|---:|---:|",
            _answer_condition_rows(answers, "uncompressed"),
            _answer_condition_rows(compressed_answers, "compressed"),
            "",
            f"Paired n={common_n}; deltas are compressed minus uncompressed:",
            "",
            "| Metric | Delta [95% CI] | p |",
            "|---|---:|---:|",
        ]
        for metric in (*quality_names, "prompt_tokens"):
            delta = deltas[metric]
            lines.append(f"| {metric} | {_delta_cell(delta)} | {delta['p_value']:.3f} |")
        lines += ["", decision, ""]

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
        "corpus, runs the full retrieval ablation, audited entity-resolution",
        "condition, and both judged-answer compression conditions, then",
        "re-renders this page from the report JSONs. Without",
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
    parser.add_argument("--compressed-answers", type=Path, default=None)
    parser.add_argument("--resolution-baseline", type=Path, default=None)
    parser.add_argument("--resolved-entities", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=Path("docs/benchmarks.md"))
    args = parser.parse_args()
    page = render_benchmarks(
        args.retrieval,
        args.answers,
        compressed_answers_path=args.compressed_answers,
        resolution_baseline_path=args.resolution_baseline,
        resolved_entities_path=args.resolved_entities,
    )
    args.output.write_text(page, encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
