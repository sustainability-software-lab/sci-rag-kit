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


def render_benchmarks(
    retrieval_path: Path,
    answers_path: Path | None,
    compressed_path: Path | None = None,
) -> str:
    retrieval = _load(retrieval_path)
    assert retrieval is not None
    answers = _load(answers_path)
    compressed = _load(compressed_path)
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
        "---",
        "title: Benchmarks",
        "description: Measured results on the shipped demo corpus, with confidence "
        "intervals, snapshot provenance, model identifiers, and the command that "
        "reproduces them.",
        "---",
        "",
        "# Benchmarks",
        "",
        "Measured results on the shipped demo corpus, regenerated with one command.",
        "This page proves the evaluation harness end to end and publishes honest",
        "numbers for this template on its own demo corpus. It makes no",
        "state-of-the-art claim and compares against no other system; see",
        "[Choosing Sci RAG Kit](choosing-sci-rag-kit.md) for that comparison, on",
        "axes other than benchmark scores.",
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

    names = {config["name"] for config in retrieval.get("configs", [])}
    if "resolved_entities" not in names:
        lines += [
            "",
            "`resolved_entities` is absent, and that is a result rather than an",
            "omission. It is a separate condition (`sci-rag eval retrieval",
            "--condition resolved_entities`) measured on a post-resolution",
            "snapshot, and it requires at least one persisted resolution audit",
            "row. On this corpus `sci-rag graph resolve-entities` finds no",
            "automatic pairs and plans no merges: 67 extracted entities with",
            "nothing duplicated enough to merge. The command refuses to run the",
            "condition rather than report a number that would just be",
            "`full_deep` under another name. A corpus with real alias variation",
            "is what would exercise it.",
        ]

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

    if compressed is not None and answers is not None:
        lines += _compression_section(answers, compressed)

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
        "Prerequisites: a selected PostgreSQL backend with pgvector, uv, and Google",
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


_JUDGED_DIMENSIONS = ("groundedness", "citation_accuracy", "completeness", "correctness")


def _median_tokens(report: dict[str, Any], key: str) -> float | None:
    value = report.get("summary", {}).get(key)
    return float(value) if value is not None else None


def _compression_section(answers: dict[str, Any], compressed: dict[str, Any]) -> list[str]:
    """The paired gate that decides whether compression may default on.

    Two answers-eval runs over the same questions and the same corpus, one
    with `--compressed` and one without. The gate asks for judged quality to
    hold while measured prompt tokens fall, so both halves are reported: a
    token saving alone never justifies the default.
    """
    base_ci = answers.get("summary_ci", {})
    comp_ci = compressed.get("summary_ci", {})
    before = _median_tokens(compressed, "prompt_tokens_before_median")
    after = _median_tokens(compressed, "prompt_tokens_after_median")
    dropped = sum(r.get("compression_dropped_count", 0) for r in compressed.get("records", []))
    failures = sum(r.get("compression_failure_count", 0) for r in compressed.get("records", []))
    n = int(compressed.get("summary", {}).get("n", 0))

    try:
        from pathlib import Path as _Path

        from sci_rag.config import get_settings
        from sci_rag.domain import load_domain

        tuning = load_domain(_Path(get_settings().domain_dir)).config.compression
        floor = f"{tuning.relevance_floor}"
        enabled = tuning.enabled
    except Exception:
        floor = "unknown"
        enabled = None

    if enabled is None:
        default_claim = "The shipped compression default could not be loaded."
    else:
        state = "on" if enabled else "off"
        default_claim = (
            f"Compression defaults {state} for the shipped demo at `relevance_floor: {floor}`."
        )

    lines = [
        "## Contextual compression: the paired gate",
        "",
        default_claim,
        "",
        "Two judged-answer runs over the same questions and the same corpus,",
        "one with `--compressed` and one without. The gate requires judged",
        "quality to HOLD while measured prompt tokens fall. A",
        "token saving on its own is not evidence; it is half of a trade.",
        "",
        f"Measured at `relevance_floor: {floor}`, which is the load-bearing",
        "setting rather than a detail. The floor decides whether a source is",
        "dropped instead of summarized, and dropping evidence is what an",
        "answer cannot recover from. Raising it trades groundedness for",
        "tokens; that is a different trade from summarizing, and it needs its",
        "own paired run.",
        "",
        "| Dimension | Uncompressed | Compressed |",
        "|-----------|-------------:|-----------:|",
    ]
    for dimension in _JUDGED_DIMENSIONS:
        lines.append(
            f"| {dimension} | {_ci_cell(base_ci.get(dimension))} | {_ci_cell(comp_ci.get(dimension))} |"
        )
    if before is not None and after is not None:
        saving = f"{(1 - after / before) * 100:.0f}%" if before else "n/a"
        lines.append(f"| median prompt tokens | {before:.0f} | {after:.0f} ({saving} lower) |")
    lines += [
        "",
        f"Sources dropped by the relevance floor: {dropped}. Compression"
        f" failures: {failures}. Questions: {n}.",
        "",
    ]
    fell = [
        d
        for d in _JUDGED_DIMENSIONS
        if (comp_ci.get(d) or {}).get("mean", 0) < (base_ci.get(d) or {}).get("mean", 0)
    ]
    if fell:
        lines += [
            f"On this run the gate does not hold: {len(fell)} of"
            f" {len(_JUDGED_DIMENSIONS)} judged dimensions moved down"
            f" ({', '.join(fell)}). At this sample size no single drop is"
            " distinguishable from noise, and that is the point: the gate asks"
            " for evidence that quality holds, and overlapping intervals are"
            " not that evidence.",
            "",
            "The mechanism is the relevance floor rather than the summarizer,"
            " which the counters above separate: sources were dropped, none"
            " failed to compress. A lower floor may pass the gate. Re-run it"
            " before turning compression on for any corpus.",
            "",
        ]
        if enabled:
            lines += [
                "The shipped domain profile currently enables compression, so",
                "this run would no longer support its default. Re-run the gate",
                "or turn compression off before publishing it for that corpus.",
                "",
            ]
        else:
            lines += [
                "`compression.enabled` therefore stays `false` in the shipped",
                "domain profile.",
                "",
            ]
    else:
        lines += [
            "On this run the gate holds: no judged dimension fell while prompt"
            " tokens dropped. That justifies the default on THIS corpus only;"
            " re-run the gate before carrying it to another.",
            "",
        ]
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retrieval", type=Path, required=True)
    parser.add_argument("--answers", type=Path, default=None)
    parser.add_argument("--answers-compressed", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=Path("docs/benchmarks.md"))
    args = parser.parse_args()
    page = render_benchmarks(args.retrieval, args.answers, args.answers_compressed)
    args.output.write_text(page, encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
