"""`sci-rag-new`: start a project from a parent directory.

The other half of the factory. `sci-rag init` specializes a checkout you
already have; this one runs where there is nothing yet, fetches the template
at the tag matching its own version, and then applies the same answers through
the same appliers.

Installed as its own entry point so the first thing a new user runs is
``pipx install sci-rag-kit && sci-rag-new``, with no repository to clone and no
files to hand-edit first.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(
    name="sci-rag-new",
    help="Create a new scientific RAG project from the sci-rag-kit template.",
    add_completion=False,
    pretty_exceptions_show_locals=False,
)
console = Console()


@app.command()
def new(
    output_dir: Path = typer.Option(
        Path("."),
        "--output-dir",
        "-o",
        help="Where to create the project directory. Defaults to the current directory.",
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
    ref: str | None = typer.Option(
        None,
        "--ref",
        help="Fetch the template at this tag or branch instead of the tag matching "
        "this generator's version.",
    ),
    template_path: Path | None = typer.Option(
        None,
        "--template-path",
        help="Generate from a local checkout instead of downloading. No network needed.",
    ),
) -> None:
    """Answer a short questionnaire, get a configured project directory."""
    from sci_rag.scaffold.answers import ProjectAnswers
    from sci_rag.scaffold.apply import apply_all
    from sci_rag.scaffold.fetch import TemplateFetchError, fetch_template
    from sci_rag.scaffold.wizard import AnswerFileError, collect_answers, confirm_ontology_draft

    non_interactive = defaults or answers_file is not None
    try:
        raw = collect_answers(defaults=defaults, answers_file=answers_file)
    except AnswerFileError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    # Built once to resolve the directory name; rebuilt after the fetch, when a
    # drafted ontology may exist to fold in.
    target = output_dir.expanduser().resolve() / ProjectAnswers.from_raw(raw).repo_name

    console.print(f"\nFetching sci-rag-kit for [bold]{target.name}[/bold]...")
    try:
        source = fetch_template(target, ref=ref, template_path=template_path)
    except TemplateFetchError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    console.print(f"  from {source}")

    drafted = None
    if raw.get("ontology") == "draft_with_llm" and raw.get("credentials") != "offline":
        if non_interactive:
            console.print(
                "[yellow]  Skipping the LLM ontology draft: accepting or redrafting one "
                "needs an interactive session. Keeping the worked example.[/yellow]"
            )
        else:
            drafted = confirm_ontology_draft(
                target / "domain",
                project_name=raw["project_name"],
                description=raw.get("description", ""),
            )

    answers = ProjectAnswers.from_raw(raw, drafted_ontology=drafted)  # type: ignore[arg-type]
    console.print(f"\nWriting [bold]{answers.repo_name}/[/bold]\n")
    for change in apply_all(answers, target):
        console.print(f"  {change}", soft_wrap=True, highlight=False)

    _print_next_steps(answers)


def _print_next_steps(answers) -> None:  # type: ignore[no-untyped-def]
    run = answers.runner.run
    console.print(f"\nDone. [bold]{answers.project_name}[/bold] is yours. Next:\n")
    console.print(f"  cd {answers.repo_name}")
    console.print(f"  {answers.runner.sync(extras=answers.extras)}")
    console.print(f"  {run('sci-rag doctor', project_slug=answers.repo_name)}")
    if answers.corpus_source in {"openalex_topic", "doi_list"}:
        console.print("  make corpus")
    elif answers.corpus_source == "demo_only":
        console.print("  make demo")
    else:
        console.print(
            f"  {run('sci-rag ingest --manifest data/corpus.jsonl', project_slug=answers.repo_name)}"
        )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
