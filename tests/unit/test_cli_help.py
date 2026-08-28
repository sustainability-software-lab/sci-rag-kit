"""CLI wiring smokes: every command parses, help renders, bad input is caught.

These run with no database and no credentials; they protect the command
surface the docs promise.
"""

import re

from typer.testing import CliRunner

from sci_rag.cli.main import app

# Rich adapts help output to the terminal (colors on CI, 80-column
# wrapping); pin a wide, colorless rendering and strip any ANSI that
# slips through so these asserts are environment-independent.
runner = CliRunner(env={"NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "300"})
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _plain(output: str) -> str:
    return _ANSI.sub("", output)


def test_root_help_lists_all_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    output = _plain(result.output)
    for command in ("ingest", "retrieve", "answer", "stats", "serve", "mcp", "doctor"):
        assert command in output
    for group in ("db", "graph", "eval", "campaign", "draft"):
        assert group in output


def test_subcommand_help_screens() -> None:
    for args in (
        ["db", "--help"],
        ["db", "upgrade", "--help"],
        ["ingest", "--help"],
        ["corpus", "--help"],
        ["corpus", "enrich", "--help"],
        ["campaign", "--help"],
        ["campaign", "discover", "--help"],
        ["campaign", "build", "--help"],
        ["graph", "--help"],
        ["graph", "extract", "--help"],
        ["graph", "communities", "--help"],
        ["graph", "resolve-entities", "--help"],
        ["draft", "--help"],
        ["draft", "questions", "--help"],
        ["draft", "manifest", "--help"],
        ["draft", "ontology", "--help"],
        ["eval", "--help"],
        ["eval", "retrieval", "--help"],
        ["eval", "answers", "--help"],
        ["retrieve", "--help"],
        ["answer", "--help"],
        ["serve", "--help"],
        ["doctor", "--help"],
    ):
        result = runner.invoke(app, args)
        assert result.exit_code == 0, f"{args}: {result.output}"


def test_documented_flags_exist() -> None:
    ingest_help = _plain(runner.invoke(app, ["ingest", "--help"]).output)
    for flag in ("--manifest", "--source", "--no-docling", "--chunk-tokens", "--overlap-tokens"):
        assert flag in ingest_help
    extract_help = _plain(runner.invoke(app, ["graph", "extract", "--help"]).output)
    for flag in ("--all", "--batch-size", "--max-chunks"):
        assert flag in extract_help
    resolve_help = _plain(runner.invoke(app, ["graph", "resolve-entities", "--help"]).output)
    for flag in ("--dry-run", "--apply", "--no-llm", "--threshold", "--llm-threshold"):
        assert flag in resolve_help
    eval_help = _plain(runner.invoke(app, ["eval", "retrieval", "--help"]).output)
    for flag in ("--ablation", "--condition", "--questions", "--limit", "--snapshot"):
        assert flag in eval_help
    answer_help = _plain(runner.invoke(app, ["answer", "--help"]).output)
    assert "--include-retracted" in answer_help
    enrich_help = _plain(runner.invoke(app, ["corpus", "enrich", "--help"]).output)
    for flag in ("--dry-run", "--limit", "--mailto"):
        assert flag in enrich_help
    campaign_help = _plain(runner.invoke(app, ["campaign", "discover", "--help"]).output)
    for flag in ("--topic", "--doi-file", "--name", "--mailto", "--max-results"):
        assert flag in campaign_help
    build_help = _plain(runner.invoke(app, ["campaign", "build", "--help"]).output)
    for flag in (
        "--topic",
        "--doi-file",
        "--name",
        "--mailto",
        "--dry-run",
        "--max-results",
        "--max-pdf-mb",
    ):
        assert flag in build_help
    doctor_help = _plain(runner.invoke(app, ["doctor", "--help"]).output)
    assert "--probe" in doctor_help


def test_ingest_rejects_ambiguous_input() -> None:
    # Neither a folder nor a manifest.
    neither = runner.invoke(app, ["ingest"])
    assert neither.exit_code != 0
    assert "exactly one" in _plain(neither.output)
    # Both at once.
    both = runner.invoke(app, ["ingest", "data/raw", "--manifest", "x.jsonl"])
    assert both.exit_code != 0
    assert "exactly one" in _plain(both.output)


def test_resolved_entity_eval_requires_a_named_snapshot() -> None:
    result = runner.invoke(app, ["eval", "retrieval", "--condition", "resolved_entities"])

    assert result.exit_code != 0
    assert "--snapshot" in _plain(result.output)
