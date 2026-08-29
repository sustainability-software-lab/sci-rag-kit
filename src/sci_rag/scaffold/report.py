"""Render the shared completion report for both scaffold entry points.

Keeping this block beside the scaffold model prevents ``sci-rag new`` and
``sci-rag init`` from teaching different first-run workflows after they apply
the same answers.
"""

from __future__ import annotations

from rich.console import Console

from sci_rag.scaffold.answers import ProjectAnswers


def print_scaffold_report(
    answers: ProjectAnswers,
    changes: list[str],
    *,
    console: Console,
    dry_run: bool = False,
    created_directory: bool = False,
) -> None:
    """Print changed files and the commands that make the project usable."""
    verb = "Would write" if dry_run else "Writing"
    console.print(f"\n{verb} [bold]{answers.repo_name}/[/bold]\n")
    for change in changes:
        console.print(f"  {change}", soft_wrap=True, highlight=False)

    if dry_run:
        console.print("\n[yellow]Dry run. Nothing was written.[/yellow]")
        console.print("Re-run without --dry-run to apply these changes.")
        return

    project_slug = answers.repo_name if created_directory else ""

    def run(command: str) -> str:
        return answers.runner.run(command, project_slug=project_slug)

    console.print(f"\nDone. [bold]{answers.project_name}[/bold] is yours. Next:\n")
    if created_directory:
        console.print(f"  cd {answers.repo_name}")
    console.print(f"  {answers.runner.sync(extras=answers.extras)}")
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
