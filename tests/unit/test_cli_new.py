"""`sci-rag-new` end to end against a local checkout.

The network path has its own tests in test_scaffold_fetch.py; these drive the
whole command, which is where the fetch, the wizard, and the appliers have to
agree about the target directory.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import yaml
from typer.testing import CliRunner

from sci_rag.cli.new import app

REPO_ROOT = Path(__file__).parents[2]
runner = CliRunner(env={"NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "300"})
_ANSI = re.compile(r"\x1b\[[0-9;]*m")

_FILES = ("pyproject.toml", "Makefile", "Dockerfile", ".env.example", "README.md", "LICENSE")
_TREES = ("domain", ".github")


def _checkout(tmp_path: Path) -> Path:
    root = tmp_path / "template"
    root.mkdir(parents=True)
    for name in _FILES:
        shutil.copy(REPO_ROOT / name, root / name)
    for tree in _TREES:
        shutil.copytree(REPO_ROOT / tree, root / tree)
    (root / "data" / "demo").mkdir(parents=True)
    (root / "data" / "demo" / "manifest.jsonl").write_text("{}\n", encoding="utf-8")
    (root / "infra" / "terraform").mkdir(parents=True)
    (root / "infra" / "terraform" / "main.tf").write_text("# tf\n", encoding="utf-8")
    return root


def test_defaults_create_a_project_directory(tmp_path: Path) -> None:
    from sci_rag.domain import load_domain

    result = runner.invoke(
        app,
        [
            "--defaults",
            "--template-path",
            str(_checkout(tmp_path)),
            "--output-dir",
            str(tmp_path / "workspace"),
        ],
    )

    assert result.exit_code == 0, result.output
    project = tmp_path / "workspace" / "my-scientific-kb"
    assert project.is_dir()
    assert load_domain(project / "domain").name == "My Scientific KB"
    assert (project / ".env").exists()


def test_the_directory_is_named_from_the_answers(tmp_path: Path) -> None:
    answers = tmp_path / "answers.yaml"
    answers.write_text(
        yaml.safe_dump({"project_name": "Membrane Materials KB", "initialize_git": "No"}),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "--answers-file",
            str(answers),
            "--template-path",
            str(_checkout(tmp_path)),
            "--output-dir",
            str(tmp_path / "workspace"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert (tmp_path / "workspace" / "membrane-materials-kb").is_dir()


def test_a_generated_project_gets_its_own_git_history(tmp_path: Path) -> None:
    """Unlike `sci-rag init`, this one creates the directory, so it may init."""
    result = runner.invoke(
        app,
        [
            "--defaults",
            "--template-path",
            str(_checkout(tmp_path)),
            "--output-dir",
            str(tmp_path / "workspace"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "workspace" / "my-scientific-kb" / ".git").is_dir()


def test_an_existing_non_empty_directory_is_refused(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    existing = workspace / "my-scientific-kb"
    existing.mkdir(parents=True)
    (existing / "mine.txt").write_text("do not touch\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "--defaults",
            "--template-path",
            str(_checkout(tmp_path)),
            "--output-dir",
            str(workspace),
        ],
    )

    assert result.exit_code == 1
    assert "not empty" in _ANSI.sub("", result.output)
    assert (existing / "mine.txt").read_text(encoding="utf-8") == "do not touch\n"


def test_the_llm_draft_is_skipped_without_an_interactive_session(tmp_path: Path) -> None:
    """--defaults answers draft_with_llm, but nobody can accept or redraft it."""
    result = runner.invoke(
        app,
        [
            "--defaults",
            "--template-path",
            str(_checkout(tmp_path)),
            "--output-dir",
            str(tmp_path / "workspace"),
        ],
    )
    output = _ANSI.sub("", result.output)
    assert "Skipping the LLM ontology draft" in output
    assert "worked example" in output


def test_next_steps_use_the_chosen_managers_commands(tmp_path: Path) -> None:
    answers = tmp_path / "answers.yaml"
    answers.write_text(
        yaml.safe_dump({"environment_manager": "pixi", "initialize_git": "No"}), encoding="utf-8"
    )
    result = runner.invoke(
        app,
        [
            "--answers-file",
            str(answers),
            "--template-path",
            str(_checkout(tmp_path)),
            "--output-dir",
            str(tmp_path / "workspace"),
        ],
    )
    output = _ANSI.sub("", result.output)
    assert "cd my-scientific-kb" in output
    assert "pixi install" in output
    assert "pixi run sci-rag doctor" in output
    assert "uv run" not in output


def test_an_unknown_answer_key_is_reported(tmp_path: Path) -> None:
    answers = tmp_path / "answers.yaml"
    answers.write_text(yaml.safe_dump({"projct_name": "typo"}), encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "--answers-file",
            str(answers),
            "--template-path",
            str(_checkout(tmp_path)),
            "--output-dir",
            str(tmp_path / "workspace"),
        ],
    )
    assert result.exit_code == 1
    assert "projct_name" in _ANSI.sub("", result.output)
