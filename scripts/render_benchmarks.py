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
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

METRICS = ("hit_at_5", "hit_at_10", "mrr", "ndcg_at_10")
METRIC_LABELS = {"hit_at_5": "hit@5", "hit_at_10": "hit@10", "mrr": "MRR", "ndcg_at_10": "nDCG@10"}


def _ci_cell(ci: dict[str, float] | None) -> str:
    if not ci:
        return "-"
    return f"{ci['mean']:.2f} [{ci['lo']:.2f}, {ci['hi']:.2f}]"


class ReportRoleError(RuntimeError):
    """Two answer reports were handed over in a shape that cannot be rendered."""


class ProvenanceError(RuntimeError):
    """A report cannot support the claims this page makes about its inputs."""


#: What a report has to carry before its numbers may be published. `snapshot`
#: and `git_commit` pin the corpus and the code; `provenance` pins the models,
#: the prompts, and the decoding, which are what move a number when neither of
#: the other two has.
REQUIRED_REPORT_FIELDS = ("git_commit", "snapshot", "provenance")

#: Fields two reports rendered onto one page have to agree about. A retrieval
#: run from one commit and an answers run from another describe neither.
SHARED_REPORT_FIELDS = ("git_commit", "snapshot", "provenance")

#: How far a published number may move before a re-render is a finding rather
#: than noise. Metrics are absolute on a 0 to 1 scale; counts are relative,
#: because a graph is built rather than measured. Both are deliberately loose:
#: the demo corpus has single-digit questions and the intervals are wide, so a
#: tighter bound would report weather.
TOLERANCES = {"metric": 0.10, "count": 0.10}

#: The counterexample to the tolerance promise above, published next to it.
#: Two reruns from identical recorded inputs moved the entity count 13.3% down
#: and 12% up, both outside the 10% count tolerance. A reader who runs the
#: command and gets a different entity count has reproduced the documented
#: behavior, and telling them so is cheaper than letting them hunt for a
#: mistake they did not make. A test holds the published page to this string,
#: so a later re-render cannot keep the numbers and drop the caveat.
GRAPH_COUNT_CAVEAT = (
    "The graph counts are the known exception to that promise. Two reruns from "
    "identical recorded inputs, the same corpus, the same models, and the same "
    "ontology, moved the entity count 13% down and 12% up. Decoding at "
    "`temperature: 0.0` does not make the extractor deterministic, and these "
    "numbers are the evidence. Read `entities` and `relationships` as one draw "
    "from a distribution. A different count on your machine is the documented "
    "behavior, not a sign that you have broken something."
)


@dataclass(frozen=True)
class PageChange:
    """One published number that moved between two renders."""

    label: str
    before: str
    after: str
    material: bool

    def describe(self) -> str:
        verdict = "MATERIAL" if self.material else "within tolerance"
        return f"  {self.label}: {self.before} -> {self.after} ({verdict})"


_COUNTS = re.compile(
    r"(?P<value>[\d,]+) (?P<label>documents|chunks|entities|relationships|communities)"
)
_TABLE_CELL = re.compile(r"^\|\s*(?P<config>[a-z_]+)\s*\|(?P<cells>.*)\|\s*$")


def _page_numbers(page: str) -> dict[str, str]:
    """Every published number, keyed by what it is.

    Read from the rendered page rather than from the reports, because the page
    is what a reader compares against and what a commit records.
    """
    numbers: dict[str, str] = {}
    for match in _COUNTS.finditer(page):
        numbers[match.group("label")] = match.group("value").replace(",", "")
    for line in page.splitlines():
        cell = _TABLE_CELL.match(line.strip())
        if cell is None:
            continue
        for index, raw in enumerate(cell.group("cells").split("|")):
            value = raw.strip()
            if value and value[0].isdigit():
                numbers[f"{cell.group('config')}[{index}]"] = value
    return numbers


def _is_material(label: str, before: str, after: str) -> bool:
    try:
        old_value = float(before.split()[0])
        new_value = float(after.split()[0])
    except (TypeError, ValueError):
        return before != after
    if label in {"documents", "chunks", "entities", "relationships", "communities"}:
        if old_value == 0:
            return new_value != 0
        return abs(new_value - old_value) / old_value > TOLERANCES["count"]
    return abs(new_value - old_value) > TOLERANCES["metric"]


def compare_pages(committed: str, rendered: str) -> list[PageChange]:
    """Every published number that moved, and whether the move is material."""
    before = _page_numbers(committed)
    after = _page_numbers(rendered)
    changes: list[PageChange] = []
    for label in sorted(set(before) | set(after)):
        old = before.get(label, "absent")
        new = after.get(label, "absent")
        if old == new:
            continue
        changes.append(PageChange(label, old, new, _is_material(label, old, new)))
    return changes


def check_against_committed(rendered: str, committed_path: Path) -> None:
    """Report every move, and refuse to pass when one is material."""
    committed = committed_path.read_text(encoding="utf-8") if committed_path.exists() else ""
    changes = compare_pages(committed, rendered)
    if not changes:
        print(f"{committed_path}: reproduced, no published number moved")
        return
    print(f"{committed_path}: {len(changes)} published number(s) moved")
    for change in changes:
        print(change.describe())
    material = [change for change in changes if change.material]
    if material:
        print(
            f"\n{len(material)} moved beyond the declared tolerance "
            f"(metrics {TOLERANCES['metric']}, counts {TOLERANCES['count']:.0%}). "
            "Publishing these numbers needs a reviewed source report and an "
            "explanation of what changed; re-run with --update once you have both."
        )
        raise SystemExit(1)


def _require_provenance(report: dict[str, Any], path: Path) -> None:
    missing = [field for field in REQUIRED_REPORT_FIELDS if not report.get(field)]
    if missing:
        raise ProvenanceError(
            f"{path} is missing {', '.join(missing)}, so its numbers cannot be published. "
            "Re-run the evaluation; reports written before the provenance contract "
            "predate these fields."
        )


def _require_agreement(first: dict[str, Any], second: dict[str, Any], where: str) -> None:
    disagree = [field for field in SHARED_REPORT_FIELDS if first.get(field) != second.get(field)]
    if disagree:
        raise ProvenanceError(
            f"{where} disagree about {', '.join(disagree)}. One page cannot describe "
            "two runs; render from reports produced by a single benchmark."
        )


def _load(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    if path.is_dir():
        path = path / "report.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _declared_compression(report: dict[str, Any], path: Path) -> bool:
    """Whether this answers run enabled compression, per its own report.

    Every answers run records `config.compression`. Reading it here is the
    whole fix: F-026 selected the two reports by directory modification time,
    and calibration updates one of those times, so the roles reversed.
    """
    config = report.get("config")
    if not isinstance(config, dict) or "compression" not in config:
        raise ReportRoleError(
            f"{path} does not record config.compression, so its role cannot be "
            "established. Re-run `sci-rag eval answers`; reports written by an "
            "older version predate the role marker."
        )
    return bool(config["compression"])


def select_answer_reports(root: Path) -> tuple[Path, Path]:
    """The newest uncompressed and compressed answers runs under ``root``.

    Ordering is by directory name, which carries the run timestamp, rather
    than by modification time, which anything writing into a directory can
    change. Roles come from each report rather than from its position.
    """
    uncompressed: Path | None = None
    compressed: Path | None = None
    for directory in sorted(root.glob("*-answers"), key=lambda path: path.name, reverse=True):
        report_path = directory / "report.json"
        if not report_path.is_file():
            continue
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if _declared_compression(report, directory):
            compressed = compressed or directory
        else:
            uncompressed = uncompressed or directory
        if uncompressed is not None and compressed is not None:
            break

    missing = [
        name
        for name, found in (("uncompressed", uncompressed), ("compressed", compressed))
        if found is None
    ]
    if missing:
        raise ReportRoleError(
            f"no {' or '.join(missing)} answers report under {root}. The paired gate "
            "needs one `sci-rag eval answers` run and one `--compressed` run."
        )
    assert uncompressed is not None and compressed is not None
    return uncompressed, compressed


def _validate_roles(
    answers: dict[str, Any] | None,
    answers_path: Path | None,
    compressed: dict[str, Any] | None,
    compressed_path: Path | None,
) -> None:
    """Refuse a pair that is reversed, duplicated, or unlabelled."""
    if answers is None or compressed is None:
        return
    assert answers_path is not None and compressed_path is not None
    if answers_path.resolve() == compressed_path.resolve():
        raise ReportRoleError(
            f"{answers_path} was given as both the ordinary and the compressed "
            "run. The paired gate compares two runs, not one against itself."
        )
    if _declared_compression(answers, answers_path):
        raise ReportRoleError(
            f"{answers_path} was given as the ordinary run but its report records "
            "config.compression = true. The two reports are the wrong way round."
        )
    if not _declared_compression(compressed, compressed_path):
        raise ReportRoleError(
            f"{compressed_path} was given as the compressed run but its report records "
            "config.compression = false. The two reports are the wrong way round."
        )


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
    _require_provenance(retrieval, retrieval_path)
    if answers is not None and answers_path is not None:
        _require_provenance(answers, answers_path)
        _require_agreement(retrieval, answers, f"{retrieval_path} and {answers_path}")
    if compressed is not None and compressed_path is not None:
        _require_provenance(compressed, compressed_path)
        _require_agreement(retrieval, compressed, f"{retrieval_path} and {compressed_path}")
    _validate_roles(answers, answers_path, compressed, compressed_path)
    calibration = _calibration_for(answers_path)
    corpus = retrieval.get("corpus", {})
    snapshot = retrieval.get("snapshot")
    commit = retrieval.get("git_commit", "unknown")
    provenance = retrieval["provenance"]
    versions = provenance.get("embedding") or (
        ", ".join(corpus.get("embedding_versions", [])) or "unknown"
    )
    # The models that produced these numbers, from the report. Reading
    # `get_settings()` here published whichever model the renderer's own shell
    # happened to name, which on a re-render is not the one that ran.
    models = provenance.get("models", {})
    llm_model = ", ".join(f"{role} `{spec}`" for role, spec in sorted(models.items())) or "unknown"
    digest = provenance.get("domain_digest", "unknown")

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
        f"- Embedding: `{versions}`; models: {llm_model}",
        f"- Code: commit `{commit}`; domain and prompts: `{digest[:12]}`",
        f"- Rendered: {datetime.now(UTC).strftime('%Y-%m-%d')}",
        "",
        "Graph construction and judged answers are stochastic. Repeating the "
        "command below reproduces these numbers within a declared tolerance of "
        f"{TOLERANCES['metric']} absolute on a metric and "
        f"{TOLERANCES['count']:.0%} on a count, and `--check` fails visibly "
        "when one moves further. A number that moves beyond it is a finding, "
        "not a refresh: publishing it needs a reviewed source report and an "
        "explanation of which recorded input changed.",
        "",
        GRAPH_COUNT_CAVEAT,
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
        "setting, not a detail. The floor decides whether a source is dropped",
        "or summarized, and dropping evidence is what an answer cannot recover",
        "from. Raising it trades groundedness for tokens; that is a different",
        "trade from summarizing, and it needs its own paired run.",
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
    # The gate has two halves. Quality holding while tokens stay flat buys
    # nothing, and the page used to call that a hold.
    tokens_fell = before is not None and after is not None and after < before
    if not fell and not tokens_fell:
        lines += [
            "On this run the gate does not hold: judged quality held, but"
            " measured prompt tokens did not fall. Compression that costs"
            " nothing and saves nothing is not evidence for a default, and"
            " the saving is the only thing it is meant to buy.",
            "",
        ]
        return lines
    if fell:
        lines += [
            f"On this run the gate does not hold: {len(fell)} of"
            f" {len(_JUDGED_DIMENSIONS)} judged dimensions moved down"
            f" ({', '.join(fell)}). At this sample size no single drop is"
            " distinguishable from noise, and that is the point: the gate asks"
            " for evidence that quality holds, and overlapping intervals are"
            " not that evidence.",
            "",
            "The mechanism is the relevance floor, not the summarizer,"
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
    parser.add_argument("--retrieval", type=Path, default=None)
    parser.add_argument("--answers", type=Path, default=None)
    parser.add_argument("--answers-compressed", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=Path("docs/benchmarks.md"))
    parser.add_argument(
        "--select-answer-roles",
        type=Path,
        default=None,
        metavar="DIR",
        help=(
            "Print the newest uncompressed answers run and the newest compressed one, "
            "one per line, and exit. Roles come from each report's own "
            "config.compression rather than from directory timestamps."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Compare the render against the committed page and exit nonzero when a "
            "published number moved beyond the declared tolerance. Writes nothing."
        ),
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help=(
            "Write the page, after printing every published number that moved. "
            "Required to overwrite committed numbers, so a refresh cannot be silent."
        ),
    )
    args = parser.parse_args()

    if args.select_answer_roles is not None:
        uncompressed, compressed = select_answer_reports(args.select_answer_roles)
        print(uncompressed)
        print(compressed)
        return

    if args.retrieval is None:
        parser.error("--retrieval is required unless --select-answer-roles is given")
    if args.check and args.update:
        parser.error("--check and --update are mutually exclusive")
    page = render_benchmarks(args.retrieval, args.answers, args.answers_compressed)

    if args.check:
        check_against_committed(page, args.output)
        return

    if not args.update:
        parser.error(
            "refusing to overwrite published numbers without --update. Run --check "
            "first to see what moved, then --update to publish it with that "
            "comparison in the change description."
        )

    committed = args.output.read_text(encoding="utf-8") if args.output.exists() else ""
    changes = compare_pages(committed, page)
    if changes:
        print(f"{args.output}: {len(changes)} published number(s) moved")
        for change in changes:
            print(change.describe())
    else:
        print(f"{args.output}: reproduced, no published number moved")
    args.output.write_text(page, encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
