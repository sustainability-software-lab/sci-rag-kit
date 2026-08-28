"""`sci-rag draft`: the assisted path to the files you would otherwise type.

Every command here offers the same three lanes, and the flags are the whole
interface to them:

* nothing extra, and the configured model drafts it (Lane A);
* ``--print-prompt``, and the rendered, corpus-grounded prompt goes to stdout
  for pasting into any assistant, then ``--from-file reply.json`` feeds the
  reply back through identical validation (Lane B);
* neither, and you write the file yourself exactly as before (Lane C).

Nothing here overwrites a file a human vouched for. A run proposes
``<file>.proposed`` and prints a summary; ``--apply`` is the separate,
deliberate step.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

draft_app = typer.Typer(
    help=(
        "Draft the domain files you would otherwise hand-write. Every drafter can also "
        "print its prompt for any assistant (--print-prompt) and read the reply back "
        "(--from-file), so no API key is required."
    ),
    no_args_is_help=True,
)

#: Every human-facing line these commands write is a diagnostic, and stdout
#: belongs to `--print-prompt` alone. The documented copy-paste lane is
#: `--print-prompt > prompt.txt`, so a status line on stdout would end up
#: pasted into the assistant along with the prompt.
console = Console(stderr=True)


def _fail(message: str) -> None:
    console.print(f"[red]{message}[/red]")
    raise typer.Exit(1)


def _gather_passages(folder: Path | None, *, count: int):  # type: ignore[no-untyped-def]
    """Passages from the ingested corpus, or from files when nothing is ingested.

    The fallback is what makes the drafters usable before ``make setup``: a
    new user has documents in a folder long before they have a database, and
    a command that refuses to run until then is a command they never reach.
    Which source ran is printed and recorded, because it changes what the
    draft could possibly have seen.
    """
    import asyncio

    from sci_rag.config import get_settings
    from sci_rag.draft import DraftError
    from sci_rag.draft.sampling import sample_corpus, sample_files

    # Enough passages to spread across a corpus without burying the
    # instructions, scaled to how many questions were asked for.
    limit = max(8, min(40, count * 3))

    if folder is not None:
        try:
            return sample_files(folder, limit=limit, per_document=3)
        except DraftError as exc:
            _fail(str(exc))

    async def from_corpus():  # type: ignore[no-untyped-def]
        from sci_rag.db import dispose_engine, get_session_factory

        try:
            return await sample_corpus(get_session_factory(), limit=limit, per_document=3)
        finally:
            # Disposed inside the loop that opened them: a pooled asyncpg
            # connection outliving asyncio.run() belongs to a loop that is gone.
            await dispose_engine()

    try:
        return asyncio.run(from_corpus())
    except Exception as corpus_exc:
        raw = get_settings().data_dir / "raw"
        console.print(
            f"[yellow]No usable ingested corpus ({type(corpus_exc).__name__}), so "
            f"drafting from {raw} instead.[/yellow]"
        )
        try:
            return sample_files(raw, limit=limit, per_document=3)
        except DraftError as file_exc:
            _fail(
                f"{file_exc}\nThe ingested corpus could not be read either: "
                f"{type(corpus_exc).__name__}: {corpus_exc}"
            )


@draft_app.command("questions")
def draft_questions_command(
    count: int = typer.Option(10, "--count", help="How many questions to ask for."),
    folder: Path | None = typer.Option(
        None,
        "--folder",
        help="Draft from documents in this folder instead of the ingested corpus.",
    ),
    print_prompt: bool = typer.Option(
        False,
        "--print-prompt",
        help="Print the rendered prompt and exit. Paste it into any assistant.",
    ),
    from_file: Path | None = typer.Option(
        None,
        "--from-file",
        help="Read the model's reply from this file instead of calling a model.",
    ),
    output: Path | None = typer.Option(
        None, "--output", help="Where to write the proposal. Defaults to <seed file>.proposed."
    ),
    apply: bool = typer.Option(
        False, "--apply", help="Append the verified questions to the seed file."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be drafted without writing anything."
    ),
    repair: bool = typer.Option(
        True,
        "--repair/--no-repair",
        help="Ask the model once more to replace rows that failed grounding verification.",
    ),
) -> None:
    """Draft seed questions grounded in your own documents, and verify them."""
    from sci_rag.cli.main import run_async
    from sci_rag.config import get_settings
    from sci_rag.domain import load_domain
    from sci_rag.draft import DraftError, proposed_path, read_reply
    from sci_rag.draft.questions import (
        DRAFTED_HEADER,
        draft_questions,
        render_jsonl,
        render_prompt,
    )

    if apply and dry_run:
        raise typer.BadParameter("--apply and --dry-run ask for opposite things")
    if count < 1:
        raise typer.BadParameter("--count must be at least 1")

    settings = get_settings()
    try:
        domain = load_domain(settings.domain_dir)
    except (FileNotFoundError, ValueError) as exc:
        _fail(str(exc))
        return

    sample = _gather_passages(folder, count=count)

    if print_prompt:
        # Deliberately bare on stdout: this output is meant to be piped to a
        # file or a clipboard, so Rich markup and panels would be damage.
        print(render_prompt(domain, sample=sample, count=count))
        return

    try:
        result = run_async(
            draft_questions(
                domain,
                sample=sample,
                count=count,
                raw_reply=read_reply(from_file) if from_file is not None else None,
                repair=repair and from_file is None,
            )
        )
    except DraftError as exc:
        _fail(str(exc))
        return

    console.print(f"Grounded in {sample.describe()}.")
    for question in result.questions:
        console.print(f"  [green]kept[/green]    {question.id}: {question.question}")
    for question_id, reason in result.dropped:
        console.print(f"  [red]dropped[/red] {question_id}: {reason}")
    for note in result.notes:
        console.print(f"  [yellow]note[/yellow]    {note}")

    if not result.questions:
        _fail("Nothing survived verification, so there is nothing to write.")
        return

    console.print(
        f"\n{len(result.questions)} verified, {len(result.dropped)} dropped. "
        "These are model-drafted and awaiting your review."
    )

    if dry_run:
        console.print("[yellow]Dry run. Nothing was written.[/yellow]")
        return

    seed_file = domain.seed_questions_path()
    if apply:
        _append_to_seed_file(seed_file, result.questions, header=DRAFTED_HEADER)
        console.print(f"Appended to [bold]{seed_file}[/bold].")
        console.print(
            "Review each one, then delete its `drafted` tag. Until you do, every "
            "evaluation report will say its ground truth is unreviewed."
        )
        return

    target = output or proposed_path(seed_file)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_jsonl(result.questions), encoding="utf-8")
    console.print(f"Proposal written to [bold]{target}[/bold].")
    console.print(
        f"Review it, then move it over {seed_file.name} yourself, or re-run with --apply."
    )


def _append_to_seed_file(seed_file: Path, questions, *, header: str) -> None:  # type: ignore[no-untyped-def]
    """Add verified rows to the seed file without disturbing what is there.

    Ids already in the file are skipped rather than replaced. The seed file is
    the expert's record, and a drafted row is never allowed to overwrite one a
    human wrote.
    """
    import json

    from sci_rag.evals.seeds import load_seed_questions

    existing = {q.id for q in load_seed_questions(seed_file)} if seed_file.exists() else set()
    fresh = [q for q in questions if q.id not in existing]
    skipped = [q.id for q in questions if q.id in existing]
    for question_id in skipped:
        console.print(
            f"  [yellow]skipped[/yellow] {question_id}: that id is already in the seed file."
        )
    if not fresh:
        console.print("[yellow]Every drafted id was already taken; nothing appended.[/yellow]")
        return

    body = "\n".join(json.dumps(question.model_dump(), ensure_ascii=False) for question in fresh)
    current = seed_file.read_text(encoding="utf-8") if seed_file.exists() else ""
    if current and not current.endswith("\n"):
        current += "\n"
    seed_file.write_text(f"{current}{header}{body}\n", encoding="utf-8")


__all__ = ["draft_app"]
