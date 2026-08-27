"""Evaluation artifacts: numbers you can trust later.

Every run writes a JSON payload (for machines and regression diffs) and a
Markdown report (for humans) into ``eval_results/``, stamped with a corpus
fingerprint (document/chunk/graph counts, embedding versions, latest
ingestion time) and the git commit when available. An eval number without
its corpus fingerprint is just a rumor.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sci_rag.db.models import Chunk, Document, KgCommunity, KgEntity, KgRelationship
from sci_rag.evals.answer_eval import AnswerEvalRecord, summarize_answer_records
from sci_rag.evals.retrieval_eval import RetrievalEvalResult


async def corpus_fingerprint(session_factory: async_sessionmaker[AsyncSession]) -> dict[str, Any]:
    async with session_factory() as session:
        counts = {}
        for label, model in (
            ("documents", Document),
            ("chunks", Chunk),
            ("entities", KgEntity),
            ("relationships", KgRelationship),
            ("communities", KgCommunity),
        ):
            counts[label] = await session.scalar(select(func.count(model.id)))
        latest = await session.scalar(select(func.max(Document.ingested_at)))
        versions = sorted(
            v
            for v in (await session.execute(select(Chunk.embedding_version).distinct())).scalars()
            if v
        )
    return {
        **counts,
        "latest_ingested_at": latest.isoformat() if latest else None,
        "embedding_versions": versions,
    }


def git_commit() -> str | None:
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            ).stdout.strip()
            or None
        )
    except Exception:
        return None


def _run_dir(base: Path, kind: str) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    directory = base / f"{stamp}-{kind}"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def write_report(
    *,
    kind: str,
    payload: dict[str, Any],
    markdown: str,
    base_dir: Path = Path("eval_results"),
) -> tuple[Path, Path]:
    directory = _run_dir(base_dir, kind)
    json_path = directory / "report.json"
    md_path = directory / "report.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    return json_path, md_path


def retrieval_payload(
    results: list[RetrievalEvalResult], fingerprint: dict[str, Any]
) -> dict[str, Any]:
    return {
        "kind": "retrieval",
        "generated_at": datetime.now(UTC).isoformat(),
        "git_commit": git_commit(),
        "corpus": fingerprint,
        "configs": [
            {
                "name": r.config.name,
                "description": r.config.description,
                "metrics": r.metrics,
                "records": [asdict(record) for record in r.records],
            }
            for r in results
        ],
    }


def retrieval_markdown(results: list[RetrievalEvalResult], fingerprint: dict[str, Any]) -> str:
    lines = [
        "# Retrieval evaluation",
        "",
        f"Corpus: {fingerprint.get('documents')} documents, {fingerprint.get('chunks')} chunks, "
        f"{fingerprint.get('entities')} entities, {fingerprint.get('communities')} communities.",
        f"Embedding versions: {', '.join(fingerprint.get('embedding_versions', [])) or 'none'}.",
        "",
        "| Config | hit@5 | hit@10 | MRR | nDCG@10 | questions |",
        "|--------|------:|-------:|----:|--------:|----------:|",
    ]
    for result in results:
        m = result.metrics
        lines.append(
            f"| {result.config.name} | {m['hit_at_5']:.2f} | {m['hit_at_10']:.2f} "
            f"| {m['mrr']:.2f} | {m.get('ndcg_at_10', 0.0):.2f} | {int(m['n'])} |"
        )
    lines += [
        "",
        "Read this table by comparing rows against `full_deep`: a layer earns",
        "its place when removing it drops hit rate or MRR. Misses by question",
        "are in report.json.",
        "",
    ]
    misses = [
        (result.config.name, record.question_id)
        for result in results
        for record in result.records
        if record.first_relevant_rank is None
    ]
    if misses:
        lines.append("## Missed questions")
        lines.append("")
        lines += [f"- `{config}`: {qid}" for config, qid in misses]
        lines.append("")
    return "\n".join(lines)


def answers_payload(records: list[AnswerEvalRecord], fingerprint: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "answers",
        "generated_at": datetime.now(UTC).isoformat(),
        "git_commit": git_commit(),
        "corpus": fingerprint,
        "summary": summarize_answer_records(records),
        "records": [asdict(record) for record in records],
    }


def answers_markdown(records: list[AnswerEvalRecord], fingerprint: dict[str, Any]) -> str:
    summary = summarize_answer_records(records)
    lines = [
        "# Answer evaluation (blind judge)",
        "",
        f"Corpus: {fingerprint.get('documents')} documents, {fingerprint.get('chunks')} chunks.",
        "",
        "Scores are 0 to 2 per dimension. The grounding judge never sees the",
        "reference answer; correctness is graded in a separate reference-only pass.",
        "",
        "| Metric | Mean |",
        "|--------|-----:|",
    ]
    for key in (
        "groundedness_mean",
        "citation_accuracy_mean",
        "completeness_mean",
        "correctness_mean",
    ):
        if key in summary:
            lines.append(f"| {key.removesuffix('_mean')} | {summary[key]:.2f} |")
    lines += [
        f"| graded / total | {int(summary['graded'])} / {int(summary['n'])} |",
        "",
        "## Per question",
        "",
        "| Question | grounded | citations | complete | correct | note |",
        "|----------|---------:|----------:|---------:|--------:|------|",
    ]
    for record in records:
        g = record.grounding
        c = record.correctness
        note = record.error or ("honesty probe" if "unanswerable" in record.tags else "")
        lines.append(
            f"| {record.question_id} "
            f"| {g.groundedness if g else '-'} "
            f"| {g.citation_accuracy if g else '-'} "
            f"| {g.completeness if g else '-'} "
            f"| {c.correctness if c else '-'} "
            f"| {note} |"
        )
    lines.append("")
    return "\n".join(lines)
