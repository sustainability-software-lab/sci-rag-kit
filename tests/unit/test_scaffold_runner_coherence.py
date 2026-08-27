"""Generate a project per environment manager and look for a sibling's commands.

This is the cheap test that catches the whole class of "the five uv-wired
surfaces disagree" bugs. A pixi project that still says `uv run` in its
Makefile, workflow, Dockerfile, README, or docs is broken on its first run,
and the failure shows up in the user's terminal rather than here unless
something asserts it.

It runs against a real copy of the template, not a fixture, so a new surface
added to the repository is covered the moment it is listed in
``apply.COHERENCE_SURFACES``.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from sci_rag.scaffold import apply
from sci_rag.scaffold.answers import ProjectAnswers
from sci_rag.scaffold.questions import default_answers
from sci_rag.scaffold.runners import PROFILES, get_runner, runner_keys

REPO_ROOT = Path(__file__).parents[2]
SLUG = "membrane-materials-kb"

# Everything an applier reads or rewrites. Copied rather than symlinked so a
# generation cannot touch the working tree.
_COPY_FILES = (
    "pyproject.toml",
    "Makefile",
    "Dockerfile",
    ".env.example",
    "README.md",
    "CONTRIBUTING.md",
    "AGENTS.md",
    "uv.lock",
)
_COPY_TREES = ("domain", "docs", "scripts", ".github", ".devcontainer", "src")


def _template(tmp_path: Path) -> Path:
    root = tmp_path / "template"
    root.mkdir(parents=True)
    for name in _COPY_FILES:
        shutil.copy(REPO_ROOT / name, root / name)
    for tree in _COPY_TREES:
        shutil.copytree(REPO_ROOT / tree, root / tree, ignore=shutil.ignore_patterns("__pycache__"))
    (root / "infra" / "terraform").mkdir(parents=True)
    (root / "infra" / "terraform" / "main.tf").write_text("# terraform\n", encoding="utf-8")
    (root / "data" / "demo").mkdir(parents=True)
    (root / "data" / "demo" / "manifest.jsonl").write_text("{}\n", encoding="utf-8")
    (root / "examples").mkdir()
    (root / "examples" / "library_quickstart.py").write_text("# example\n", encoding="utf-8")
    return root


def _generate(tmp_path: Path, manager: str) -> Path:
    root = _template(tmp_path)
    raw = dict(default_answers())
    raw.update(
        {
            "project_name": "Membrane Materials KB",
            "repo_name": SLUG,
            "environment_manager": manager,
            "initialize_git": "No",
        }
    )
    apply.apply_all(ProjectAnswers.from_raw(raw), root, year=2026)
    return root


@pytest.mark.parametrize("manager", runner_keys())
def test_no_other_managers_commands_survive(tmp_path: Path, manager: str) -> None:
    root = _generate(tmp_path, manager)
    chosen = get_runner(manager)
    siblings = [profile for profile in PROFILES.values() if profile.key != manager]

    offenders: list[str] = []
    for path in apply.coherence_files(root):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for sibling in siblings:
            for token in sibling.command_tokens():
                # A token another manager also legitimately uses is not
                # evidence of a leak (venv+pip and uv both build venvs).
                if token in chosen.command_tokens():
                    continue
                if token in text:
                    offenders.append(f"{path.relative_to(root)}: {sibling.key} token {token!r}")

    assert not offenders, "\n".join(sorted(set(offenders)))


@pytest.mark.parametrize("manager", runner_keys())
def test_the_chosen_manager_actually_reaches_the_five_surfaces(
    tmp_path: Path, manager: str
) -> None:
    root = _generate(tmp_path, manager)
    profile = get_runner(manager)

    makefile = (root / "Makefile").read_text(encoding="utf-8")
    workflow = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    devcontainer = json.loads(
        (root / ".devcontainer" / "devcontainer.json").read_text(encoding="utf-8")
    )
    quickstart = (root / "docs" / "quickstart.md").read_text(encoding="utf-8")

    assert profile.sync() in makefile
    assert profile.ci_setup_action in workflow
    assert profile.sync() in workflow
    prefix = profile.run("", project_slug=SLUG)
    if prefix:
        assert prefix in makefile
        assert prefix in quickstart
    if profile.devcontainer_feature:
        assert profile.devcontainer_feature in devcontainer["features"]
    assert profile.sync() in devcontainer["postCreateCommand"]
    # The Dockerfile is rendered whole from the profile rather than patched.
    assert dockerfile == profile.dockerfile(python_version="3.12", project_slug=SLUG)


@pytest.mark.parametrize("manager", runner_keys())
def test_only_the_chosen_managers_lockfile_is_present(tmp_path: Path, manager: str) -> None:
    root = _generate(tmp_path, manager)
    profile = get_runner(manager)
    for other in PROFILES.values():
        if other.lockfile and other.lockfile != profile.lockfile:
            assert not (root / other.lockfile).exists(), other.lockfile


@pytest.mark.parametrize("manager", runner_keys())
def test_the_chosen_managers_manifest_exists(tmp_path: Path, manager: str) -> None:
    root = _generate(tmp_path, manager)
    assert (root / get_runner(manager).manifest).exists()


def test_generated_workflows_are_valid_yaml(tmp_path: Path) -> None:
    """A rewritten setup block that broke indentation would fail here first."""
    import yaml

    for manager in runner_keys():
        root = _generate(tmp_path / manager, manager)
        for workflow in sorted((root / ".github" / "workflows").glob("*.yml")):
            parsed = yaml.safe_load(workflow.read_text(encoding="utf-8"))
            assert parsed["jobs"], f"{manager}: {workflow.name}"


@pytest.mark.parametrize("manager", runner_keys())
def test_the_kits_own_matrix_workflow_does_not_ship(tmp_path: Path, manager: str) -> None:
    """It generates projects, so a generated project must not carry it."""
    root = _generate(tmp_path, manager)
    assert not (root / ".github" / "workflows" / "generated-projects.yml").exists()
