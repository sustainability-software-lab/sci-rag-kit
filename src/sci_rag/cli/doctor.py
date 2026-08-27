"""`sci-rag doctor`: check the whole setup in one command.

Runs through configuration, domain profile, database, schema, corpus,
graph, and credentials, and prints a table of findings with a fix hint
for anything wrong. Static by default (no model calls); `--probe` adds a
live round-trip through the embedding and generation models.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import typer
from rich.console import Console
from rich.table import Table

console = Console()

_PROMPT_FILES = (
    "entity_extraction",
    "query_entities",
    "hyde",
    "answer",
    "community_summary",
    "judge_grounding",
    "judge_correctness",
)
_LATEST_SCHEMA_REVISION = "0005"


@dataclass
class Check:
    name: str
    status: str  # "ok" | "warn" | "fail"
    detail: str
    fix: str = ""


def doctor(
    probe: bool = typer.Option(
        False, "--probe", help="Also make one tiny live embedding and generation call."
    ),
) -> None:
    """Diagnose the environment: config, domain, database, corpus, credentials."""
    import asyncio

    checks = asyncio.run(_run_checks(probe=probe))

    table = Table(title="sci-rag doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")
    table.add_column("Fix", overflow="fold")
    icon = {"ok": "[green]ok[/green]", "warn": "[yellow]warn[/yellow]", "fail": "[red]FAIL[/red]"}
    for check in checks:
        table.add_row(check.name, icon[check.status], check.detail, check.fix)
    console.print(table)

    failures = [c for c in checks if c.status == "fail"]
    if failures:
        console.print(f"[red]{len(failures)} check(s) failed.[/red]")
        raise typer.Exit(1)
    console.print("[green]All checks passed.[/green]")


async def _run_checks(*, probe: bool) -> list[Check]:
    from sci_rag.config import get_settings

    settings = get_settings()
    checks: list[Check] = []

    # --- configuration -------------------------------------------------
    mode = settings.credentials_mode()
    checks.append(
        Check(
            "config",
            "ok",
            f"embedding={settings.embedding_provider}:{settings.embedding_model}@{settings.embedding_dim}, "
            f"llm={settings.llm_model}, credentials={mode}",
        )
    )
    if settings.embedding_provider == "google" and mode == "none":
        checks.append(
            Check(
                "credentials",
                "fail",
                "The google embedding provider is selected but no credentials are set.",
                "Set SCI_RAG_GOOGLE_API_KEY or SCI_RAG_GCP_PROJECT in .env, or use "
                "SCI_RAG_EMBEDDING_PROVIDER=local-hash for an offline dry run.",
            )
        )
    elif mode == "none":
        checks.append(
            Check(
                "credentials",
                "warn",
                "No Google credentials: retrieval works, generation and graph build will not.",
                "Set SCI_RAG_GOOGLE_API_KEY (or SCI_RAG_GCP_PROJECT) in .env.",
            )
        )
    else:
        checks.append(Check("credentials", "ok", f"mode={mode}"))

    # --- domain profile -------------------------------------------------
    try:
        from sci_rag.domain import load_domain

        domain = load_domain(settings.domain_dir)
        missing_prompts = [
            name
            for name in _PROMPT_FILES
            if not (domain.directory / "prompts" / f"{name}.md").exists()
        ]
        if missing_prompts:
            checks.append(
                Check(
                    "domain",
                    "fail",
                    f"missing prompt template(s): {', '.join(missing_prompts)}",
                    "Restore them from the template's domain/prompts/ directory.",
                )
            )
        else:
            checks.append(
                Check(
                    "domain",
                    "ok",
                    f"{domain.name!r}: {len(domain.entity_type_names)} entity types, "
                    f"{len(domain.relation_type_names)} relation types, "
                    f"{len(domain.config.query_classes)} query classes",
                )
            )
    except Exception as exc:
        checks.append(
            Check(
                "domain",
                "fail",
                f"{type(exc).__name__}: {exc}",
                "Fix domain/domain.yaml (see domain/README.md).",
            )
        )
        domain = None

    if domain is not None:
        try:
            from sci_rag.evals import load_seed_questions

            questions = load_seed_questions(domain.seed_questions_path())
            probes = sum(1 for q in questions if not q.answerable)
            status = "ok" if questions else "warn"
            note = f"{len(questions)} seed question(s), {probes} honesty probe(s)"
            checks.append(
                Check(
                    "seed questions",
                    status,
                    note,
                    "" if questions else "Write ground-truth questions before trusting any eval.",
                )
            )
        except FileNotFoundError:
            checks.append(
                Check(
                    "seed questions",
                    "warn",
                    "domain/eval_seed_questions.jsonl not found",
                    "Create it (see docs/evaluation.md); evals need ground truth.",
                )
            )
        except Exception as exc:
            checks.append(
                Check(
                    "seed questions",
                    "fail",
                    f"{type(exc).__name__}: {exc}",
                    "Fix the JSONL (one valid JSON object per line).",
                )
            )

    # --- parser availability ---------------------------------------------
    from sci_rag.ingest import docling_available

    if docling_available():
        checks.append(Check("pdf parser", "ok", "docling installed"))
    else:
        checks.append(
            Check(
                "pdf parser",
                "warn",
                "docling not installed; PDFs fall back to pypdf (reduced table fidelity)",
                "uv sync --extra docling",
            )
        )

    # --- database ---------------------------------------------------------
    from sqlalchemy import text

    from sci_rag.db import dispose_engine, get_engine

    engine = get_engine()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        checks.append(
            Check(
                "database",
                "fail",
                f"cannot connect ({type(exc).__name__})",
                "docker compose up -d --wait, or fix SCI_RAG_DATABASE_URL in .env.",
            )
        )
        await dispose_engine()
        return checks
    checks.append(Check("database", "ok", settings.database_url.split("@")[-1]))

    async with engine.connect() as conn:
        vector_version = await conn.scalar(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        )
        if vector_version is None:
            available = await conn.scalar(
                text("SELECT count(*) FROM pg_available_extensions WHERE name = 'vector'")
            )
            checks.append(
                Check(
                    "pgvector",
                    "fail",
                    "extension not installed in this database"
                    + ("" if available else " (and not available on this server)"),
                    "Run sci-rag db upgrade (it creates the extension), or use the "
                    "bundled docker-compose Postgres, which ships pgvector.",
                )
            )
            await dispose_engine()
            return checks
        checks.append(Check("pgvector", "ok", f"version {vector_version}"))

        revision = None
        try:
            revision = await conn.scalar(text("SELECT version_num FROM alembic_version"))
        except Exception:
            await conn.rollback()
        if revision is None:
            checks.append(
                Check(
                    "schema",
                    "fail",
                    "tables not created yet",
                    "uv run sci-rag db upgrade",
                )
            )
            await dispose_engine()
            return checks
        if revision != _LATEST_SCHEMA_REVISION:
            checks.append(
                Check(
                    "schema",
                    "fail",
                    f"migration revision {revision}; expected {_LATEST_SCHEMA_REVISION}",
                    "uv run sci-rag db upgrade",
                )
            )
            await dispose_engine()
            return checks
        checks.append(Check("schema", "ok", f"migration revision {revision}"))

        column_dim = await conn.scalar(
            text(
                "SELECT atttypmod FROM pg_attribute "
                "WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'"
            )
        )
        if column_dim is not None and column_dim > 0 and column_dim != settings.embedding_dim:
            checks.append(
                Check(
                    "embedding dimension",
                    "fail",
                    f"database column is vector({column_dim}) but settings say {settings.embedding_dim}",
                    "Align SCI_RAG_EMBEDDING_DIM with the column, or recreate the "
                    "schema and re-ingest (see docs/quickstart.md troubleshooting).",
                )
            )
        else:
            checks.append(Check("embedding dimension", "ok", f"vector({settings.embedding_dim})"))

        documents = await conn.scalar(text("SELECT count(*) FROM documents")) or 0
        chunks = await conn.scalar(text("SELECT count(*) FROM chunks")) or 0
        unembedded = (
            await conn.scalar(text("SELECT count(*) FROM chunks WHERE embedding IS NULL")) or 0
        )
        if documents == 0:
            checks.append(
                Check(
                    "corpus",
                    "warn",
                    "empty",
                    "uv run sci-rag ingest --manifest data/demo/manifest.jsonl (or your own corpus)",
                )
            )
        elif unembedded:
            checks.append(
                Check(
                    "corpus",
                    "warn",
                    f"{documents} documents, {chunks} chunks, {unembedded} without embeddings",
                    "Re-run ingestion for the affected documents.",
                )
            )
        else:
            checks.append(Check("corpus", "ok", f"{documents} documents, {chunks} chunks"))

        retracted = (
            await conn.scalar(
                text(
                    "SELECT count(*) FROM documents "
                    "WHERE extra #>> '{crossref,is_retracted}' = 'true'"
                )
            )
            or 0
        )
        if retracted:
            checks.append(
                Check(
                    "retractions",
                    "warn",
                    f"{retracted} document(s) are flagged as retracted",
                    "Answers exclude them by default. Review them and use "
                    "sci-rag corpus delete when they should leave the corpus.",
                )
            )
        else:
            checks.append(Check("retractions", "ok", "no known retracted documents"))

        if chunks:
            from sci_rag.embed import get_embedder

            current_version = get_embedder(settings).version
            stale_chunks = (
                await conn.scalar(
                    text(
                        "SELECT count(*) FROM chunks WHERE embedding_version IS DISTINCT FROM :v"
                    ).bindparams(v=current_version)
                )
                or 0
            )
            stale_communities = (
                await conn.scalar(
                    text(
                        "SELECT count(*) FROM kg_communities WHERE summary IS NOT NULL "
                        "AND summary_embedding_version IS DISTINCT FROM :v"
                    ).bindparams(v=current_version)
                )
                or 0
            )
            if stale_chunks or stale_communities:
                checks.append(
                    Check(
                        "embedding versions",
                        "warn",
                        f"{stale_chunks} chunk(s) and {stale_communities} community "
                        f"summar(ies) not on {current_version}",
                        "uv run sci-rag embed reindex --apply",
                    )
                )
            else:
                checks.append(Check("embedding versions", "ok", f"all rows on {current_version}"))

        orphaned = (
            await conn.scalar(
                text(
                    "SELECT count(*) FROM kg_entities "
                    "WHERE chunk_ids = '{}' AND document_ids = '{}' "
                    "AND canonical_entity_id IS NULL"
                )
            )
            or 0
        )
        if orphaned:
            checks.append(
                Check(
                    "graph hygiene",
                    "warn",
                    f"{orphaned} entit(ies) with no evidence (left by deletions)",
                    "uv run sci-rag graph gc --apply",
                )
            )

        duplicate_candidates = (
            await conn.scalar(
                text(
                    "WITH surfaces AS ("
                    "SELECT id, entity_type, lower(regexp_replace(name, '[^[:alnum:]]+', '', 'g')) "
                    "AS normalized FROM kg_entities WHERE canonical_entity_id IS NULL) "
                    "SELECT count(*) FROM ("
                    "SELECT entity_type, normalized FROM surfaces "
                    "WHERE normalized <> '' GROUP BY entity_type, normalized HAVING count(*) > 1"
                    ") duplicate_groups"
                )
            )
            or 0
        )
        if duplicate_candidates:
            checks.append(
                Check(
                    "entity resolution",
                    "warn",
                    f"{duplicate_candidates} exact normalized duplicate group(s)",
                    "uv run sci-rag graph resolve-entities --dry-run",
                )
            )
        else:
            checks.append(Check("entity resolution", "ok", "no exact normalized duplicates"))

        entities = await conn.scalar(text("SELECT count(*) FROM kg_entities")) or 0
        communities = await conn.scalar(text("SELECT count(*) FROM kg_communities")) or 0
        if documents and not entities:
            checks.append(
                Check(
                    "knowledge graph",
                    "warn",
                    "no entities yet (graph and community layers will return nothing)",
                    "uv run sci-rag graph extract && uv run sci-rag graph communities",
                )
            )
        else:
            checks.append(
                Check("knowledge graph", "ok", f"{entities} entities, {communities} communities")
            )

    # --- live probe -------------------------------------------------------
    if probe:
        checks.extend(await _live_probe(settings))

    await dispose_engine()
    return checks


async def _live_probe(settings) -> list[Check]:  # type: ignore[no-untyped-def]
    checks: list[Check] = []
    try:
        from sci_rag.embed import get_embedder

        embedder = get_embedder(settings)
        start = time.monotonic()
        [vector] = await embedder.embed(["doctor probe"], task="query")
        checks.append(
            Check(
                "embedding probe",
                "ok",
                f"{embedder.version}, {len(vector)} dims, {int((time.monotonic() - start) * 1000)} ms",
            )
        )
    except Exception as exc:
        checks.append(
            Check(
                "embedding probe",
                "fail",
                f"{type(exc).__name__}: {str(exc)[:120]}",
                "Check credentials and SCI_RAG_EMBEDDING_MODEL.",
            )
        )
    try:
        from sci_rag.llm import get_llm

        llm = get_llm(settings)
        start = time.monotonic()
        reply = await llm.generate("Reply with the single word: ready", max_tokens=10)
        checks.append(
            Check(
                "generation probe",
                "ok" if reply.strip() else "warn",
                f"{getattr(llm, 'model', settings.llm_model)}, "
                f"{int((time.monotonic() - start) * 1000)} ms",
            )
        )
    except Exception as exc:
        checks.append(
            Check(
                "generation probe",
                "fail",
                f"{type(exc).__name__}: {str(exc)[:120]}",
                "Check credentials and SCI_RAG_LLM_MODEL.",
            )
        )
    return checks
