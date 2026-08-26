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
    report = asyncio.run(
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
        retriever = Retriever()
        return await retriever.retrieve(
            query, profile=profile, limit=limit, scope=_scope(license_classes, sources)
        )

    result = asyncio.run(run())

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
                        line = f"  [{c['index']}] {c['title']}"
                        if c["citation"]:
                            line += f". {c['citation']}"
                        console.print(line)
            elif event.type == "error":
                console.print(f"\n[red]{event.data['message']}[/red]")
                raise typer.Exit(1)
        console.print()

    asyncio.run(run())


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
    stats_result = asyncio.run(
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
    stats_result = asyncio.run(
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

    counts, by_license, versions = asyncio.run(run())
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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
