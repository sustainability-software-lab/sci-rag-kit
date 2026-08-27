"""The sci-rag command line.

Run everything from the repository root (paths in settings are resolved
relative to where you run the command):

    sci-rag db upgrade            # create/upgrade the database schema
    sci-rag ingest data/raw       # ingest a folder (or --manifest file.jsonl)
    sci-rag retrieve "question"   # inspect retrieval: ranked chunks + traces
    sci-rag answer "question"     # a grounded, cited answer
    sci-rag stats                 # what is in the knowledge base
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="sci-rag",
    help="A DIY GraphRAG factory for scientific domains.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)
db_app = typer.Typer(help="Database schema management.", no_args_is_help=True)
app.add_typer(db_app, name="db")
graph_app = typer.Typer(
    help="Build the knowledge graph: extract entities, then detect communities.",
    no_args_is_help=True,
)
app.add_typer(graph_app, name="graph")
eval_app = typer.Typer(
    help="Measure your RAG honestly: retrieval metrics, layer ablations, judged answers.",
    no_args_is_help=True,
)
app.add_typer(eval_app, name="eval")
embed_app = typer.Typer(
    help="Embedding maintenance: find and re-embed rows left behind by a model upgrade.",
    no_args_is_help=True,
)
app.add_typer(embed_app, name="embed")
corpus_app = typer.Typer(
    help="Corpus lifecycle: delete documents cleanly, snapshot what you have.",
    no_args_is_help=True,
)
app.add_typer(corpus_app, name="corpus")

console = Console()


def find_repo_root() -> Path:
    """Walk up from the current directory to the folder holding alembic.ini."""
    current = Path.cwd()
    for candidate in [current, *current.parents]:
        if (candidate / "alembic.ini").exists():
            return candidate
    raise typer.BadParameter(
        "Could not find alembic.ini above the current directory. "
        "Run sci-rag commands from inside your sci-rag-kit repository."
    )


def run_async(coro):  # type: ignore[no-untyped-def]
    """asyncio.run with the common first-run failures translated into
    short, actionable messages instead of tracebacks."""
    from sci_rag.config import get_settings

    try:
        return asyncio.run(coro)
    except Exception as exc:
        text = f"{type(exc).__name__}: {exc}"
        lowered = text.lower()
        if "does not exist" in lowered and ("relation" in lowered or "table" in lowered):
            console.print(
                "[red]The database schema is missing.[/red] Create it with:\n"
                "  [bold]uv run sci-rag db upgrade[/bold]"
            )
        elif any(
            marker in lowered
            for marker in (
                "connection refused",
                "connect call failed",
                "connection was closed",
                "name or service not known",
                "nodename nor servname",
            )
        ):
            console.print(
                f"[red]Cannot reach Postgres[/red] at "
                f"[bold]{get_settings().database_url.split('@')[-1]}[/bold].\n"
                "Start it with [bold]docker compose up -d --wait[/bold] "
                "(or point SCI_RAG_DATABASE_URL at your own Postgres), then retry.\n"
                "Run [bold]uv run sci-rag doctor[/bold] for a full checkup."
            )
        elif "no google credentials configured" in lowered:
            console.print(f"[red]{exc}[/red]")
        else:
            raise
        raise typer.Exit(1) from None


async def _check_db() -> None:
    """Fail fast with a clear message when Postgres is unreachable.

    Retrieval itself degrades per stage by design, which is right for a
    server but misleading in a terminal: a dead database would read as
    "no results". A cheap SELECT 1 up front turns that into the real story.
    """
    from sqlalchemy import text

    from sci_rag.db import get_engine

    async with get_engine().connect() as conn:
        await conn.execute(text("SELECT 1"))


def _scope(license_classes: str | None, sources: str | None):  # type: ignore[no-untyped-def]
    from sci_rag.retrieve import RetrievalScope

    return RetrievalScope(
        license_classes=tuple(x.strip() for x in license_classes.split(","))
        if license_classes
        else None,
        sources=tuple(x.strip() for x in sources.split(",")) if sources else None,
    )


@db_app.command("upgrade")
def db_upgrade() -> None:
    """Create or upgrade the database schema (runs the Alembic migrations)."""
    from alembic import command as alembic_command
    from alembic.config import Config as AlembicConfig

    root = find_repo_root()
    config = AlembicConfig(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    alembic_command.upgrade(config, "head")
    console.print("[green]Database schema is up to date.[/green]")


@app.command()
def ingest(
    path: Path | None = typer.Argument(
        None, help="Folder of documents to ingest (PDF, Markdown, or plain text)."
    ),
    manifest: Path | None = typer.Option(
        None, "--manifest", "-m", help="A JSONL corpus manifest with per-document metadata."
    ),
    source: str = typer.Option(
        "local", "--source", help="Source label recorded on documents ingested from a folder."
    ),
    no_docling: bool = typer.Option(
        False, "--no-docling", help="Skip Docling even if installed (use the pypdf fallback)."
    ),
    chunk_tokens: int = typer.Option(800, help="Target tokens per chunk."),
    overlap_tokens: int = typer.Option(150, help="Overlap tokens between chunks."),
) -> None:
    """Ingest documents: parse, chunk, embed, and store them."""
    from sci_rag.config import get_settings
    from sci_rag.embed import get_embedder
    from sci_rag.ingest import discover_folder, ingest_entries, load_manifest

    if (path is None) == (manifest is None):
        raise typer.BadParameter("Provide exactly one of: a folder PATH, or --manifest FILE.")
    entries = load_manifest(manifest) if manifest else discover_folder(path, source=source)  # type: ignore[arg-type]
    if not entries:
        console.print("[yellow]Nothing to ingest: no supported files found.[/yellow]")
        raise typer.Exit(1)
    console.print(f"Ingesting [bold]{len(entries)}[/bold] document(s)...")

    embedder = get_embedder(get_settings())
    report = run_async(
        ingest_entries(
            entries,
            embedder=embedder,
            target_tokens=chunk_tokens,
            overlap_tokens=overlap_tokens,
            prefer_docling=not no_docling,
        )
    )

    table = Table(title="Ingestion report")
    table.add_column("Document")
    table.add_column("Status")
    table.add_column("Chunks", justify="right")
    table.add_column("Detail")
    for outcome in report.outcomes:
        color = {"ingested": "green", "skipped_duplicate": "yellow", "failed": "red"}[
            outcome.status
        ]
        table.add_row(
            Path(outcome.path).name,
            f"[{color}]{outcome.status}[/{color}]",
            str(outcome.chunk_count or ""),
            outcome.detail,
        )
    console.print(table)
    console.print(
        f"[green]{report.ingested} ingested[/green], "
        f"[yellow]{report.skipped} skipped[/yellow], "
        f"[red]{report.failed} failed[/red]."
    )
    if report.failed:
        raise typer.Exit(1)


@app.command()
def retrieve(
    query: str = typer.Argument(..., help="The question to search for."),
    profile: str = typer.Option("deep", help="Retrieval profile: interactive or deep."),
    limit: int = typer.Option(8, help="How many fused results to return."),
    license_classes: str | None = typer.Option(
        None, "--license", help="Comma-separated license allowlist (e.g. public,open_commercial)."
    ),
    sources: str | None = typer.Option(None, "--source", help="Comma-separated source allowlist."),
) -> None:
    """Inspect retrieval: see what each layer contributed and what won."""
    from sci_rag.retrieve import Retriever

    async def run():  # type: ignore[no-untyped-def]
        await _check_db()
        retriever = Retriever()
        return await retriever.retrieve(
            query, profile=profile, limit=limit, scope=_scope(license_classes, sources)
        )

    result = run_async(run())

    trace_table = Table(title=f"Retrieval stages ({profile} profile)")
    trace_table.add_column("Stage")
    trace_table.add_column("Status")
    trace_table.add_column("ms", justify="right")
    trace_table.add_column("Candidates", justify="right")
    for trace in result.traces:
        color = {
            "success": "green",
            "empty": "cyan",
            "disabled": "dim",
            "skipped": "yellow",
            "timeout": "red",
            "error": "red",
            "denied": "red",
        }.get(trace.status, "white")
        trace_table.add_row(
            trace.stage,
            f"[{color}]{trace.status}[/{color}]",
            str(trace.duration_ms or ""),
            str(trace.candidate_count or ""),
        )
    console.print(trace_table)

    if not result.items:
        console.print("[yellow]No results within the current scope.[/yellow]")
        raise typer.Exit(0)
    for i, item in enumerate(result.items, start=1):
        header = f"[bold]{i}. {item.title}[/bold]"
        if item.section_path:
            header += f" [dim]({item.section_path})[/dim]"
        console.print(header)
        console.print(
            f"   score={item.score:.4f} layers={'+'.join(item.layers)} "
            f"license={item.license_class} kind={item.kind}"
        )
        preview = item.content.replace("\n", " ")
        console.print(f"   [dim]{preview[:220]}{'...' if len(preview) > 220 else ''}[/dim]")


@app.command()
def answer(
    query: str = typer.Argument(..., help="The question to answer."),
    profile: str = typer.Option("deep", help="Retrieval profile: interactive or deep."),
    limit: int = typer.Option(8, help="How many sources to give the model."),
    license_classes: str | None = typer.Option(None, "--license"),
    sources: str | None = typer.Option(None, "--source"),
) -> None:
    """Generate a grounded answer with numbered citations."""
    from sci_rag.answer import AnswerEngine

    async def run() -> None:
        await _check_db()
        engine = AnswerEngine()
        console.print(f"[dim]Retrieving ({profile} profile)...[/dim]")
        async for event in engine.answer_stream(
            query, profile=profile, limit=limit, scope=_scope(license_classes, sources)
        ):
            if event.type == "retrieval_done":
                degraded = event.data["degraded_stages"]
                note = f" (degraded: {', '.join(degraded)})" if degraded else ""
                console.print(
                    f"[dim]{event.data['item_count']} sources retrieved{note}. Generating...[/dim]\n"
                )
            elif event.type == "delta":
                console.print(event.data["text"], end="")
            elif event.type == "citations":
                cited = [c for c in event.data["citations"] if c["cited"]]
                if cited:
                    console.print("\n\n[bold]Sources[/bold]")
                    for c in cited:
                        console.print(f"  [{c['index']}] {c['citation'] or c['title']}")
            elif event.type == "error":
                console.print(f"\n[red]{event.data['message']}[/red]")
                raise typer.Exit(1)
        console.print()

    run_async(run())


@graph_app.command("extract")
def graph_extract(
    batch_size: int = typer.Option(10, help="Chunks per extraction call."),
    reprocess_all: bool = typer.Option(
        False, "--all", help="Re-read every chunk, not just unprocessed ones."
    ),
    max_chunks: int | None = typer.Option(None, help="Stop after this many chunks (for trials)."),
) -> None:
    """Extract entities and relationships from ingested chunks (needs an LLM)."""
    from sci_rag.config import get_settings
    from sci_rag.db import get_session_factory
    from sci_rag.domain import load_domain
    from sci_rag.graph import extract_graph
    from sci_rag.llm import get_llm

    settings = get_settings()
    stats_result = run_async(
        extract_graph(
            session_factory=get_session_factory(),
            llm=get_llm(settings, model=settings.resolved_extraction_model),
            domain=load_domain(settings.domain_dir),
            batch_size=batch_size,
            reprocess_all=reprocess_all,
            max_chunks=max_chunks,
        )
    )
    console.print(
        f"Processed [bold]{stats_result.chunks_processed}[/bold] chunk(s): "
        f"[green]{stats_result.entities_created} entities created[/green], "
        f"{stats_result.entities_updated} enriched, "
        f"[green]{stats_result.relationships_created} relationships created[/green], "
        f"[red]{stats_result.batches_failed} batch(es) failed[/red]."
    )
    if stats_result.batches_failed:
        console.print("[yellow]Failed batches stay unprocessed; rerun to retry them.[/yellow]")
        raise typer.Exit(1)


@graph_app.command("communities")
def graph_communities(
    min_size: int = typer.Option(3, help="Smallest cluster worth summarizing."),
) -> None:
    """Cluster the graph and write LLM summaries (rebuilds all communities)."""
    from sci_rag.config import get_settings
    from sci_rag.db import get_session_factory
    from sci_rag.domain import load_domain
    from sci_rag.embed import get_embedder
    from sci_rag.graph import build_communities
    from sci_rag.llm import get_llm

    settings = get_settings()
    stats_result = run_async(
        build_communities(
            session_factory=get_session_factory(),
            llm=get_llm(settings),
            embedder=get_embedder(settings),
            domain=load_domain(settings.domain_dir),
            min_size=min_size,
        )
    )
    console.print(
        f"[green]{stats_result.communities_created} communities[/green] covering "
        f"{stats_result.entities_clustered} entities."
        + (
            f" [yellow]{stats_result.llm_summary_failures} summaries fell back to entity lists.[/yellow]"
            if stats_result.llm_summary_failures
            else ""
        )
    )


def _load_questions(questions_path: Path | None):  # type: ignore[no-untyped-def]
    from sci_rag.config import get_settings
    from sci_rag.evals import load_seed_questions

    path = questions_path or (get_settings().domain_dir / "eval_seed_questions.jsonl")
    questions = load_seed_questions(path)
    if not questions:
        console.print(f"[red]No questions found in {path}.[/red]")
        raise typer.Exit(1)
    return questions


def _print_retrieval_results(results) -> None:  # type: ignore[no-untyped-def]
    table = Table(title="Retrieval metrics")
    table.add_column("Config")
    table.add_column("hit@5", justify="right")
    table.add_column("hit@10", justify="right")
    table.add_column("MRR", justify="right")
    table.add_column("n", justify="right")
    for result in results:
        m = result.metrics
        table.add_row(
            result.config.name,
            f"{m['hit_at_5']:.2f}",
            f"{m['hit_at_10']:.2f}",
            f"{m['mrr']:.2f}",
            str(int(m["n"])),
        )
    console.print(table)


@eval_app.command("retrieval")
def eval_retrieval(
    questions_path: Path | None = typer.Option(None, "--questions", help="Seed questions JSONL."),
    limit: int = typer.Option(10, help="Results retrieved per question."),
    ablation: bool = typer.Option(
        False, "--ablation", help="Run every layer-ablation config, not just full_deep."
    ),
) -> None:
    """Score retrieval against your seed questions (and per-layer ablations)."""
    from sci_rag.db import get_session_factory
    from sci_rag.evals import DEFAULT_ABLATIONS, run_retrieval_eval
    from sci_rag.evals.report import (
        corpus_fingerprint,
        retrieval_markdown,
        retrieval_payload,
        write_report,
    )
    from sci_rag.retrieve import Retriever

    questions = _load_questions(questions_path)
    configs = DEFAULT_ABLATIONS if ablation else DEFAULT_ABLATIONS[:1]

    async def run():  # type: ignore[no-untyped-def]
        retriever = Retriever()
        results = await run_retrieval_eval(retriever, questions, configs=configs, limit=limit)
        fingerprint = await corpus_fingerprint(get_session_factory())
        return results, fingerprint

    results, fingerprint = run_async(run())
    _print_retrieval_results(results)
    json_path, md_path = write_report(
        kind="retrieval-ablation" if ablation else "retrieval",
        payload=retrieval_payload(results, fingerprint),
        markdown=retrieval_markdown(results, fingerprint),
    )
    console.print(f"Report written to [bold]{md_path}[/bold] (and {json_path.name}).")


@eval_app.command("answers")
def eval_answers(
    questions_path: Path | None = typer.Option(None, "--questions", help="Seed questions JSONL."),
    profile: str = typer.Option("deep", help="Retrieval profile for answer generation."),
    limit: int = typer.Option(8, help="Sources per answer."),
    judge_model: str | None = typer.Option(
        None, help="Judge model id (defaults to the answer model)."
    ),
) -> None:
    """Generate answers for every seed question and grade them with the blind judge."""
    from sci_rag.answer import AnswerEngine
    from sci_rag.config import get_settings
    from sci_rag.db import get_session_factory
    from sci_rag.evals import run_answer_eval
    from sci_rag.evals.report import (
        answers_markdown,
        answers_payload,
        corpus_fingerprint,
        write_report,
    )
    from sci_rag.llm import get_llm

    questions = _load_questions(questions_path)
    settings = get_settings()

    async def run():  # type: ignore[no-untyped-def]
        engine = AnswerEngine(settings=settings)
        judge = get_llm(settings, model=judge_model) if judge_model else get_llm(settings)
        records = await run_answer_eval(engine, judge, questions, profile=profile, limit=limit)
        fingerprint = await corpus_fingerprint(get_session_factory())
        return records, fingerprint

    records, fingerprint = run_async(run())
    from sci_rag.evals import summarize_answer_records

    summary = summarize_answer_records(records)
    table = Table(title="Answer evaluation (0 to 2 per dimension)")
    table.add_column("Metric")
    table.add_column("Mean", justify="right")
    for key, value in summary.items():
        table.add_row(key, f"{value:.2f}")
    console.print(table)
    json_path, md_path = write_report(
        kind="answers",
        payload=answers_payload(records, fingerprint),
        markdown=answers_markdown(records, fingerprint),
    )
    console.print(f"Report written to [bold]{md_path}[/bold] (and {json_path.name}).")


@eval_app.command("diff")
def eval_diff(
    report_a: Path = typer.Argument(..., help="Baseline report.json (or its run directory)."),
    report_b: Path = typer.Argument(..., help="Comparison report.json (or its run directory)."),
    config: str | None = typer.Option(
        None, "--config", help="Diff only this ablation config (default: every common config)."
    ),
    output: Path | None = typer.Option(
        None, "--output", help="Also write the markdown diff to this path."
    ),
) -> None:
    """Compare two eval runs: per-question rank moves and paired metric deltas.

    Deltas are B minus A. Run it after any retrieval-affecting change to
    see whether the improvement is real or inside the noise.
    """
    from sci_rag.evals.diff import DiffError, diff_markdown, diff_reports, load_report

    try:
        payload_a = load_report(report_a)
        payload_b = load_report(report_b)
        diff = diff_reports(payload_a, payload_b, config=config)
    except DiffError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    markdown = diff_markdown(diff)
    console.print(markdown)
    if output is not None:
        output.write_text(markdown, encoding="utf-8")
        console.print(f"Diff written to [bold]{output}[/bold].")


@eval_app.command("calibrate")
def eval_calibrate(
    labels: Path = typer.Option(..., "--labels", help="Human labels (labels.jsonl)."),
    report: Path | None = typer.Option(
        None,
        "--report",
        help="Answers report.json (or its run directory) to calibrate against. "
        "Defaults to the newest answers run under eval_results/.",
    ),
    output: Path | None = typer.Option(
        None, "--output", help="Also write the calibration markdown to this path."
    ),
) -> None:
    """Compare human labels against the judge's scores: Cohen's kappa per dimension.

    Appends a calibration section to the report's markdown (report.md) and
    writes calibration.json next to it, so the kappa travels with the eval
    numbers it qualifies.
    """
    from sci_rag.evals.calibration import (
        CalibrationError,
        calibrate,
        calibration_markdown,
        judge_scores_from_report,
        parse_labels,
    )
    from sci_rag.evals.diff import DiffError, load_report

    try:
        if report is None:
            candidates = sorted(Path("eval_results").glob("*-answers/report.json"))
            if not candidates:
                raise CalibrationError(
                    "no --report given and no answers run found under eval_results/"
                )
            report = candidates[-1]
            console.print(f"Using newest answers report: [bold]{report}[/bold]")
        payload = load_report(report)
        result = calibrate(parse_labels(labels), judge_scores_from_report(payload))
    except (CalibrationError, DiffError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    markdown = calibration_markdown(result)
    console.print(markdown)
    report_path = report / "report.json" if report.is_dir() else report
    calibration_json = report_path.parent / "calibration.json"
    calibration_json.write_text(json.dumps(result.as_dict(), indent=2), encoding="utf-8")
    report_md = report_path.parent / "report.md"
    if report_md.exists():
        report_md.write_text(
            report_md.read_text(encoding="utf-8").rstrip() + "\n\n" + markdown + "\n",
            encoding="utf-8",
        )
        console.print(f"Calibration appended to [bold]{report_md}[/bold].")
    console.print(f"Calibration data written to [bold]{calibration_json}[/bold].")
    if output is not None:
        output.write_text(markdown, encoding="utf-8")


@embed_app.command("reindex")
def embed_reindex(
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--apply",
        help="--dry-run (default) reports what is stale; --apply re-embeds it.",
    ),
    batch_size: int = typer.Option(32, help="Rows re-embedded per batch (one commit per batch)."),
) -> None:
    """Re-embed chunks and community summaries stamped with a retired embedder version.

    A dimension change is refused outright: that is a schema migration
    plus a full re-ingest, never a reindex.
    """
    from sci_rag.config import get_settings
    from sci_rag.db import get_session_factory
    from sci_rag.embed import get_embedder
    from sci_rag.embed.planner import ReindexRefused, apply_reindex, plan_reindex

    embedder = get_embedder(get_settings())

    async def run():  # type: ignore[no-untyped-def]
        await _check_db()
        factory = get_session_factory()
        plan = await plan_reindex(factory, embedder)
        outcome = None
        if not dry_run and not plan.clean:
            outcome = await apply_reindex(
                factory, embedder, batch_size=batch_size, progress=console.print
            )
        return plan, outcome

    try:
        plan, outcome = run_async(run())
    except ReindexRefused as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    table = Table(title=f"Re-embed plan (current embedder: {plan.embedder_version})")
    table.add_column("What")
    table.add_column("Count", justify="right")
    table.add_row("chunks total", str(plan.total_chunks))
    table.add_row("chunks stale", str(plan.stale_chunks))
    for version, count in sorted(plan.chunk_versions.items(), key=lambda kv: str(kv[0])):
        table.add_row(f"  from {version or 'unstamped'}", str(count))
    table.add_row("community summaries stale", str(plan.stale_communities))
    console.print(table)

    if plan.clean:
        console.print("[green]Everything is already on the current embedding version.[/green]")
    elif dry_run:
        console.print("Dry run: nothing written. Re-run with [bold]--apply[/bold] to re-embed.")
    elif outcome is not None:
        console.print(
            f"[green]Re-embedded {outcome.chunks_reembedded} chunk(s) and "
            f"{outcome.communities_reembedded} community summar(ies) "
            f"in {outcome.batches} batch(es).[/green]"
        )


@corpus_app.command("delete")
def corpus_delete(
    document_ids: list[str] = typer.Argument(..., help="Document id(s) to delete."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt."),
) -> None:
    """Delete documents and every graph trace of their evidence.

    Chunks cascade, entity evidence arrays are scrubbed, relationships
    evidenced by the documents go, and communities that aggregated that
    evidence are dropped (rebuild them with `sci-rag graph communities`).
    Run `sci-rag graph gc` afterwards to sweep entities left with no
    evidence at all.
    """
    from sci_rag.corpus import delete_documents
    from sci_rag.db import get_session_factory

    if not yes:
        typer.confirm(
            f"Delete {len(document_ids)} document(s) and scrub their graph evidence?",
            abort=True,
        )

    async def run():  # type: ignore[no-untyped-def]
        await _check_db()
        return await delete_documents(get_session_factory(), document_ids)

    outcome = run_async(run())
    if outcome.documents_deleted == 0:
        console.print("[yellow]No matching documents found; nothing deleted.[/yellow]")
        raise typer.Exit(1)
    console.print(
        f"[green]Deleted {outcome.documents_deleted} document(s)[/green]: "
        f"{outcome.chunks_deleted} chunk(s) cascaded, "
        f"{outcome.entities_scrubbed} entit(ies) scrubbed, "
        f"{outcome.relationships_deleted} relationship(s) removed, "
        f"{outcome.communities_deleted} communit(ies) dropped."
    )
    if outcome.communities_deleted:
        console.print(
            "Rebuild community coverage with [bold]sci-rag graph communities[/bold]; "
            "sweep evidence-less entities with [bold]sci-rag graph gc --apply[/bold]."
        )


@graph_app.command("gc")
def graph_gc_command(
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--apply",
        help="--dry-run (default) reports what would go; --apply removes it.",
    ),
) -> None:
    """Garbage-collect the graph: evidence-less entities, dangling
    relationships, communities whose members no longer resolve."""
    from sci_rag.corpus import graph_gc
    from sci_rag.db import get_session_factory

    async def run():  # type: ignore[no-untyped-def]
        await _check_db()
        return await graph_gc(get_session_factory(), dry_run=dry_run)

    outcome = run_async(run())
    table = Table(title="Graph GC" + (" (dry run)" if dry_run else ""))
    table.add_column("What")
    table.add_column("Count", justify="right")
    table.add_row("evidence-less entities", str(outcome.entities_deleted))
    table.add_row("dangling relationships", str(outcome.relationships_deleted))
    table.add_row("communities dropped", str(outcome.communities_deleted))
    table.add_row("communities pruned", str(outcome.communities_pruned))
    console.print(table)
    if outcome.clean:
        console.print("[green]Graph is clean; nothing to collect.[/green]")
    elif dry_run:
        console.print("Dry run: nothing removed. Re-run with [bold]--apply[/bold].")
    else:
        console.print(
            "[green]Swept.[/green] Rebuild community coverage with "
            "[bold]sci-rag graph communities[/bold] if communities were dropped."
        )


@app.command()
def stats() -> None:
    """What is in the knowledge base right now."""
    from sqlalchemy import func, select

    from sci_rag.db import (
        Chunk,
        Document,
        KgCommunity,
        KgEntity,
        KgRelationship,
        get_session_factory,
    )

    async def run():  # type: ignore[no-untyped-def]
        async with get_session_factory()() as session:
            counts = {}
            for label, model in (
                ("documents", Document),
                ("chunks", Chunk),
                ("entities", KgEntity),
                ("relationships", KgRelationship),
                ("communities", KgCommunity),
            ):
                counts[label] = await session.scalar(select(func.count(model.id)))
            by_license = (
                await session.execute(
                    select(Document.license_class, func.count(Document.id)).group_by(
                        Document.license_class
                    )
                )
            ).all()
            versions = (
                await session.execute(
                    select(Chunk.embedding_version, func.count(Chunk.id)).group_by(
                        Chunk.embedding_version
                    )
                )
            ).all()
        return counts, by_license, versions

    counts, by_license, versions = run_async(run())
    table = Table(title="Knowledge base")
    table.add_column("Thing")
    table.add_column("Count", justify="right")
    for label, count in counts.items():
        table.add_row(label, str(count))
    console.print(table)
    if by_license:
        console.print("Licenses: " + ", ".join(f"{lc}={n}" for lc, n in by_license))
    if versions:
        console.print("Embedding versions: " + ", ".join(f"{v}={n}" for v, n in versions))


@app.command()
def serve(
    host: str | None = typer.Option(None, help="Bind address (default from settings)."),
    port: int | None = typer.Option(
        None, help="Port (default from settings; Cloud Run sets PORT)."
    ),
) -> None:
    """Serve the REST API (/v1, docs at /docs) and the MCP server (/mcp)."""
    import os

    import uvicorn

    from sci_rag.config import get_settings
    from sci_rag.server import create_app

    settings = get_settings()
    resolved_port = port or int(os.environ.get("PORT", settings.server_port))
    resolved_host = host or settings.server_host
    console.print(
        f"Serving on [bold]http://{resolved_host}:{resolved_port}[/bold] "
        f"(docs at /docs, MCP at /mcp)."
    )
    uvicorn.run(create_app(settings=settings), host=resolved_host, port=resolved_port)


@app.command("mcp")
def mcp_stdio() -> None:
    """Run the MCP server over stdio (for local agents like Claude Code).

    Add it to an agent with, for example:
    claude mcp add sci-rag -- uv run --directory /path/to/your/repo sci-rag mcp
    """
    import logging
    import sys

    import structlog

    # stdout carries the MCP protocol; every log line must go to stderr.
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    structlog.configure(
        logger_factory=structlog.PrintLoggerFactory(sys.stderr),
    )

    from sci_rag.server import RagService, build_mcp_server

    service = RagService()
    mcp_server, _tools = build_mcp_server(service)
    mcp_server.run()


from sci_rag.cli.doctor import doctor as _doctor  # noqa: E402 - registered after app exists

app.command("doctor")(_doctor)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
