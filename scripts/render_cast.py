"""Render Quick and Advanced onboarding transcripts and terminal casts.

The session on the documentation homepage is not typed by hand. It is produced
by driving the real wizard with a scripted set of answers and capturing exactly
what it printed, so a question added to ``sci_rag.scaffold.questions`` shows up
here or ``--check`` fails. A hand-recorded cast goes stale the first time
someone edits the question list, silently, on the page a new user reads first.

Three artifacts come out of two runs:

* ``docs/assets/casts/sci-rag-new.cast``, the recommended Quick session.
* ``docs/assets/casts/sci-rag-new-advanced.cast``, the full Advanced session.
* both static transcripts in ``docs/index.md``, with Advanced collapsed.

The only stubbed part is the model call behind the ontology draft: it uses the
mock LLM client the tests use, so the drafting output is the real rendering
code over a canned response rather than a live generation. Everything else,
including the change log and the closing next steps, is the program's own
output for these answers.
"""

from __future__ import annotations

import argparse
import io
import json
import shutil
from pathlib import Path

from rich.console import Console

from sci_rag.llm import MockLLM
from sci_rag.scaffold.answers import ProjectAnswers
from sci_rag.scaffold.apply import apply_all
from sci_rag.scaffold.report import print_scaffold_report
from sci_rag.scaffold.wizard import collect_answers, confirm_ontology_draft

REPO_ROOT = Path(__file__).resolve().parents[1]
BEGIN = "<!-- BEGIN GENERATED TRANSCRIPT: scripts/render_cast.py -->"
END = "<!-- END GENERATED TRANSCRIPT -->"

# The Advanced session exercises every gated branch. Blank values still press
# Enter, so questions added later appear without needing another hand-built
# positional list.
ADVANCED_ANSWERS = {
    "project_name": "Membrane Materials KB",
    "description": "Membrane chemistry and performance for water treatment",
    "author_name": "Berkeley Lab",
    "contact_email": "you@lbl.gov",
    "environment_manager": "2",
    "credentials": "1",
    "ontology": "1",
    "corpus_source": "2",
    "openalex_topic": "polyamide membrane fouling",
    "max_results": "250",
    "pdf_parser": "2",
    "include_terraform": "2",
    "include_demo_corpus": "2",
}

QUICK_ANSWERS = {
    "project_name": "Membrane Materials KB",
    "description": "Membrane chemistry and performance for water treatment",
    "contact_email": "you@lbl.gov",
    "environment_manager": "1",
    "credentials": "1",
    "corpus_source": "1",
}

# The response the mock model gives for the ontology draft. Kept here rather
# than generated so the page is byte-stable between runs.
DRAFTED_ONTOLOGY = json.dumps(
    {
        "entity_types": [
            {"name": "Membrane", "description": "A separation layer"},
            {"name": "Material", "description": "What a membrane is made of"},
            {"name": "Contaminant", "description": "Something removed from water"},
            {"name": "Process", "description": "A treatment or fabrication step"},
            {"name": "Property", "description": "A measured characteristic"},
            {"name": "Application", "description": "Where the membrane is used"},
            {"name": "Organization", "description": "A lab, agency, or vendor"},
            {"name": "Standard", "description": "A test method or specification"},
        ],
        "relation_types": [
            {"name": "MADE_OF"},
            {"name": "REMOVES"},
            {"name": "HAS_PROPERTY"},
            {"name": "USED_IN"},
            {"name": "REQUIRES"},
            {"name": "COMPARED_WITH"},
        ],
        "query_classes": [
            {"name": "performance", "keywords": ["flux", "rejection"]},
            {"name": "fabrication", "keywords": ["casting", "coating"]},
            {"name": "fouling", "keywords": ["fouling", "cleaning"]},
            {"name": "application", "keywords": ["desalination", "reuse"]},
        ],
    }
)

# Files an applier reads or rewrites, copied into a scratch tree so rendering
# the page never touches the working directory.
_TEMPLATE_FILES = ("pyproject.toml", "Makefile", "Dockerfile", ".env.example", "README.md")
_TEMPLATE_TREES = ("domain", ".github", ".devcontainer")


def _input_stream(*, quick: bool) -> io.StringIO:
    """One line per visible prompt, including the setup-mode pre-step."""
    from sci_rag.scaffold.questions import QUESTIONS, default_for, is_asked

    scripted = QUICK_ANSWERS if quick else ADVANCED_ANSWERS
    replies = ["1" if quick else "2"]
    gathered: dict[str, str] = {}
    for question in QUESTIONS:
        if not is_asked(question, gathered):
            continue
        default = default_for(question, gathered)
        reply = scripted.get(question.name, "")
        if quick and not question.quick:
            gathered[question.name] = default
            continue
        replies.append(reply)
        if not reply:
            gathered[question.name] = default
        elif question.choices and reply.isdigit():
            gathered[question.name] = question.choices[int(reply) - 1]
        else:
            gathered[question.name] = reply
    return io.StringIO("\n".join(replies) + "\n")


def _scratch_template(root: Path) -> Path:
    target = root / "template"
    target.mkdir(parents=True)
    for name in _TEMPLATE_FILES:
        shutil.copy(REPO_ROOT / name, target / name)
    for tree in _TEMPLATE_TREES:
        shutil.copytree(
            REPO_ROOT / tree, target / tree, ignore=shutil.ignore_patterns("__pycache__")
        )
    for extra in ("infra/terraform", "data/demo", "examples", "docs/planning"):
        (target / extra).mkdir(parents=True, exist_ok=True)
        (target / extra / ".keep").write_text("", encoding="utf-8")
    return target


def render_transcript(*, quick: bool = True) -> str:
    """One complete Quick or Advanced session, as the program prints it."""
    import tempfile

    output = io.StringIO()
    output.write("$ pipx install sci-rag-kit\n$ sci-rag new\n")

    raw = collect_answers(input_stream=_input_stream(quick=quick), output_stream=output)

    drafted = confirm_ontology_draft(
        REPO_ROOT / "domain",
        project_name=raw["project_name"],
        description=raw["description"],
        llm=MockLLM(responses=[DRAFTED_ONTOLOGY]),
        input_stream=io.StringIO("\n"),
        output_stream=output,
    )
    answers = ProjectAnswers.from_raw(raw, drafted_ontology=drafted)  # type: ignore[arg-type]

    with tempfile.TemporaryDirectory() as scratch:
        template = _scratch_template(Path(scratch))
        output.write(f"\nFetching sci-rag-kit for {answers.repo_name}...\n")
        changes = apply_all(answers, template, year=2026)

    print_scaffold_report(
        answers,
        changes,
        console=Console(file=output, color_system=None, force_terminal=False, width=300),
        created_directory=True,
    )
    # Pressing Enter leaves the prompt with a trailing space. The
    # trailing-whitespace pre-commit hook would strip it from the committed
    # page and make --check fail forever, so strip it at the source.
    return "".join(f"{line.rstrip()}\n" for line in output.getvalue().splitlines())


def render_cast(transcript: str) -> str:
    """An asciicast v2 file, one event per line of the transcript.

    Timings are synthesized rather than measured. The point of the player is to
    show the shape of the session at a readable pace; a real wall clock would
    mostly record how fast the person typing was.
    """
    width = max((len(line) for line in transcript.splitlines()), default=80) + 2
    header = {
        "version": 2,
        "width": max(width, 80),
        "height": 24,
        "title": "sci-rag-new (generated by scripts/render_cast.py)",
        "env": {"TERM": "xterm-256color", "SHELL": "/bin/bash"},
    }
    lines = [json.dumps(header, separators=(",", ":"))]
    clock = 0.0
    for line in transcript.splitlines():
        # Prompts read as typing; output lines land at once.
        clock += 0.45 if line.rstrip().endswith(":") else 0.12
        lines.append(json.dumps([round(clock, 3), "o", line + "\r\n"], separators=(",", ":")))
    clock += 2.0
    lines.append(json.dumps([round(clock, 3), "o", ""], separators=(",", ":")))
    return "\n".join(lines) + "\n"


def render_index(index_text: str, quick: str, advanced: str) -> str:
    """Replace the generated block in docs/index.md, leaving the rest alone."""
    if BEGIN not in index_text or END not in index_text:
        raise SystemExit(
            f"docs/index.md is missing the generated-transcript markers ({BEGIN}). "
            "Add them around the example session block."
        )
    head, _, rest = index_text.partition(BEGIN)
    _, _, tail = rest.partition(END)
    block = (
        f'{BEGIN}\n\n```console title="Terminal"\n{quick}```\n\n'
        "<details markdown>\n<summary>Show the Advanced setup</summary>\n\n"
        '<div class="srag-cast" data-cast="assets/casts/sci-rag-new-advanced.cast" '
        'aria-label="Recorded Advanced sci-rag new session"></div>\n\n'
        f'```console title="Terminal"\n{advanced}```\n\n</details>\n\n{END}'
    )
    return head + block + tail


def _write_or_check(path: Path, content: str, *, check: bool) -> int:
    if check:
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            print(f"stale generated artifact: {path}; run make cast")
            return 1
        print(f"up to date: {path}")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"wrote {path}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cast", type=Path, default=Path("docs/assets/casts/sci-rag-new.cast"))
    parser.add_argument(
        "--advanced-cast",
        type=Path,
        default=Path("docs/assets/casts/sci-rag-new-advanced.cast"),
    )
    parser.add_argument("--index", type=Path, default=Path("docs/index.md"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    quick = render_transcript(quick=True)
    advanced = render_transcript(quick=False)
    status = _write_or_check(args.cast, render_cast(quick), check=args.check)
    status |= _write_or_check(args.advanced_cast, render_cast(advanced), check=args.check)
    status |= _write_or_check(
        args.index,
        render_index(args.index.read_text(encoding="utf-8"), quick, advanced),
        check=args.check,
    )
    raise SystemExit(status)


if __name__ == "__main__":
    main()
