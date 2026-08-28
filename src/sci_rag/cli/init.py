"""`sci-rag init`: run the setup wizard inside a checkout you already have.

This is the in-repository half of the project factory. `sci-rag-new` fetches
the template first and then runs exactly this logic; here the template is the
directory you are standing in, which is why nothing in this command touches
git history.

A dry run applies the change to a scratch copy of the checkout and reports
what came out, so the preview is produced by the same appliers as the real
run rather than by a second description of them that could drift.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import typer
from rich.console import Console

# Copies for a dry run skip anything large or regenerable. None of it is read
# by an applier, and data/raw can hold a whole corpus.
_SCRATCH_IGNORE = shutil.ignore_patterns(
    ".git",
    ".venv",
    "__pycache__",
    "*.pyc",
    "site",
    "eval_results",
    "raw",
    "interim",
    "processed",
    "snapshots",
    "node_modules",
)

console = Console()


def init(
    target: Path = typer.Option(
        Path("."), "--target", help="The checkout to specialize. Defaults to the current directory."
    ),
    defaults: bool = typer.Option(
        False, "--defaults", help="Take every default without asking. Useful in CI."
    ),
    answers_file: Path | None = typer.Option(
        None,
        "--answers-file",
        help="A YAML file of answers, for reproducible generation. Unanswered questions "
        "take their default.",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would change without writing anything."
    ),
) -> None:
    """Specialize this checkout for your own domain.

    Asks about your project, credentials, ontology, corpus, and stack, then
    rewrites the configuration files in place. Everything it writes is a file
    you are meant to keep editing afterwards; nothing is generated code.
    """
    from sci_rag.scaffold.answers import ProjectAnswers
    from sci_rag.scaffold.apply import apply_all
    from sci_rag.scaffold.wizard import AnswerFileError, collect_answers, confirm_ontology_draft

    root = target.expanduser().resolve()
    if not (root / "pyproject.toml").exists() or not (root / "domain").is_dir():
        console.print(
            f"[red]{root} does not look like a sci-rag-kit checkout[/red] "
            "(no pyproject.toml and domain/ directory). Run this from inside the "
            "repository, or pass --target."
        )
        raise typer.Exit(1)

    try:
        raw = collect_answers(defaults=defaults, answers_file=answers_file)
    except AnswerFileError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    drafted = None
    if raw.get("ontology") == "draft_with_llm" and raw.get("credentials") != "offline":
        if defaults or answers_file is not None:
            console.print(
                "[yellow]Skipping the LLM ontology draft: accepting or redrafting one "
                "needs an interactive session. Keeping the worked example.[/yellow]"
            )
        else:
            drafted = confirm_ontology_draft(
                root / "domain",
                project_name=raw["project_name"],
                description=raw.get("description", ""),
            )
    answers = ProjectAnswers.from_raw(raw, drafted_ontology=drafted)  # type: ignore[arg-type]

    if dry_run:
        with tempfile.TemporaryDirectory() as scratch:
            preview = Path(scratch) / root.name
            shutil.copytree(root, preview, ignore=_SCRATCH_IGNORE, symlinks=True)
            changes = apply_all(answers, preview, allow_git=False)
        _report(answers, changes, dry_run=True)
        return

    changes = apply_all(answers, root, allow_git=False)
    _report(answers, changes, dry_run=False)


def _report(answers, changes: list[str], *, dry_run: bool) -> None:  # type: ignore[no-untyped-def]
    verb = "Would write" if dry_run else "Writing"
    console.print(f"\n{verb} [bold]{answers.repo_name}/[/bold]\n")
    for change in changes:
        # soft_wrap keeps the aligned columns intact in a narrow terminal;
        # this block is the transcript the documentation shows.
        console.print(f"  {change}", soft_wrap=True, highlight=False)

    if dry_run:
        console.print("\n[yellow]Dry run. Nothing was written.[/yellow]")
        console.print("Re-run without --dry-run to apply these changes.")
        return

    run = answers.runner.run
    console.print(f"\nDone. [bold]{answers.project_name}[/bold] is yours. Next:\n")
    console.print(f"  {answers.runner.sync_command}")
    console.print(f"  {run('sci-rag doctor')}")
    if answers.corpus_source in {"openalex_topic", "doi_list"}:
        console.print("  make corpus")
    elif answers.corpus_source == "demo_only":
        console.print("  make demo")
    else:
        if answers.draft_domain_files:
            console.print(f"  {run('sci-rag draft manifest --folder data/raw')}")
        console.print(f"  {run('sci-rag ingest --manifest data/corpus.jsonl')}")

    if answers.draft_domain_files:
        console.print("\nThen let a model draft the rest of your domain files:\n")
        console.print(f"  {run('sci-rag draft ontology --from-corpus')}")
        console.print(f"  {run('sci-rag draft questions --count 10')}")
        console.print(
            "\nEach one proposes a file for you to review rather than writing one, and "
            "each also prints its prompt (--print-prompt) if you would rather paste it "
            "into an assistant you already have. Guide: docs/llm-assisted-setup.md"
        )
    else:
        console.print(
            "\nThen write domain/domain.yaml, data/corpus.jsonl, and "
            "domain/eval_seed_questions.jsonl by hand. If you change your mind, "
            "`sci-rag draft --help` does a first pass at all three."
        )
    console.print("\nThe walkthrough: docs/bring-your-own-domain.md")
