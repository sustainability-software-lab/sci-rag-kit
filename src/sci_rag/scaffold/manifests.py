"""Dependency manifests for the managers that need one of their own.

uv reads `pyproject.toml` directly and needs nothing here. pixi reads it too
but wants its own tables; conda and pip each want a separate file. All three
are derived from the project's real dependency lists rather than from a
duplicated copy, so a dependency added to `pyproject.toml` reaches every
manager without a second edit.

The task tables and command strings all come from the runner profile, so this
module names no manager-specific command of its own.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

import yaml

from sci_rag.scaffold.answers import ProjectAnswers

# pixi resolves per platform. These three cover the laptops and CI runners the
# kit is developed and tested on; a user on another platform adds it here.
PIXI_PLATFORMS = ("osx-arm64", "osx-64", "linux-64")

# The Makefile is the portable entry point for every manager, but pixi users
# expect `pixi run <task>` to work natively, so the targets are mirrored.
# `setup` is absent on purpose: for pixi that is `pixi install` itself.
_MIRRORED_TASKS = {
    "db-upgrade": "sci-rag db upgrade",
    "test": "pytest",
    "typecheck": "mypy",
    "serve": "sci-rag serve",
    "mcp": "sci-rag mcp",
    "doctor": "sci-rag doctor",
    "eval": "sci-rag eval retrieval",
}


@dataclass(frozen=True)
class Dependencies:
    runtime: list[str]
    dev: list[str]
    docs: list[str]
    extras: dict[str, list[str]]


def read_dependencies(root: Path) -> Dependencies:
    parsed = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    project = parsed.get("project", {})
    groups = parsed.get("dependency-groups", {})
    return Dependencies(
        runtime=list(project.get("dependencies", [])),
        dev=list(groups.get("dev", [])),
        docs=list(groups.get("docs", [])),
        extras={
            name: list(deps) for name, deps in project.get("optional-dependencies", {}).items()
        },
    )


def _selected_extra_requirements(answers: ProjectAnswers, deps: Dependencies) -> list[str]:
    selected: list[str] = []
    for extra in answers.extras:
        selected.extend(deps.extras.get(extra, []))
    return selected


# --- pixi -------------------------------------------------------------------


def _pixi_tables(answers: ProjectAnswers, deps: Dependencies, *, standalone: bool) -> str:
    prefix = "" if standalone else "tool.pixi."
    profile = answers.runner
    features = ", ".join(f'"{extra}"' for extra in ["dev", *answers.extras])
    tasks = "\n".join(
        f'{name} = "{command}"' for name, command in _pixi_task_commands(answers, profile).items()
    )
    platforms = ", ".join(f'"{platform}"' for platform in PIXI_PLATFORMS)
    return f"""
[{prefix}workspace]
channels = ["conda-forge"]
platforms = [{platforms}]

# Python comes from conda-forge; everything else resolves from PyPI so the
# dependency list stays single-sourced in [project].
[{prefix}dependencies]
python = "{answers.python_version}.*"

[{prefix}pypi-dependencies]
{answers.repo_name} = {{ path = ".", editable = true }}

[{prefix}environments]
default = {{ features = [{features}], solve-group = "default" }}

# `make` is the portable entry point for every manager; these mirror it so
# `pixi run test` works natively too.
[{prefix}tasks]
{tasks}
"""


def lint_paths(answers: ProjectAnswers) -> str:
    """The directories ruff is pointed at, which pruning can change.

    `ruff check` exits non-zero on a path that does not exist, so this has to
    agree with what the pruning applier left behind.
    """
    return "src tests examples scripts" if answers.include_demo_corpus else "src tests scripts"


def _pixi_task_commands(answers: ProjectAnswers, profile: object) -> dict[str, str]:
    del profile  # tasks run inside the environment, so they carry no prefix
    commands = dict(_MIRRORED_TASKS)
    commands["lint"] = f"ruff check {lint_paths(answers)}"
    commands["format"] = f"ruff format {lint_paths(answers)}"
    if answers.include_demo_corpus:
        commands["demo"] = "sci-rag ingest --manifest data/demo/manifest.jsonl"
    if answers.corpus_source == "openalex_topic":
        commands["corpus"] = (
            f'sci-rag campaign build --topic "{answers.openalex_topic}" '
            f"--max-results {answers.max_results}"
        )
    elif answers.corpus_source == "doi_list":
        commands["corpus"] = "sci-rag campaign build --doi-file data/dois.txt"
    return commands


def write_pixi(answers: ProjectAnswers, root: Path) -> list[str]:
    deps = read_dependencies(root)
    standalone = answers.dependency_file == "pixi.toml"
    tables = _pixi_tables(answers, deps, standalone=standalone)

    if standalone:
        header = (
            "# pixi manifest. The dependency lists live in pyproject.toml; this file\n"
            "# only carries the pixi-specific workspace, environment, and task tables.\n"
        )
        (root / "pixi.toml").write_text(header + tables.lstrip("\n"), encoding="utf-8")
        return ["pixi.toml              workspace, environments, tasks"]

    path = root / "pyproject.toml"
    path.write_text(path.read_text(encoding="utf-8").rstrip("\n") + "\n" + tables, encoding="utf-8")
    return ["pyproject.toml         [tool.pixi] workspace, environments, tasks"]


# --- conda ------------------------------------------------------------------


def write_conda(answers: ProjectAnswers, root: Path) -> list[str]:
    """An environment.yml that installs the project itself through pip.

    Only Python comes from conda-forge. Resolving the runtime dependencies
    there too would mean maintaining a second dependency list that could drift
    from `[project.dependencies]`, and pip inside a conda environment is the
    normal way scientific projects handle exactly this.
    """
    deps = read_dependencies(root)
    pip_requirements = [
        "-e .",
        *_selected_extra_requirements(answers, deps),
        *deps.dev,
    ]
    document = {
        "name": answers.repo_name,
        "channels": ["conda-forge"],
        "dependencies": [
            f"python={answers.python_version}",
            "pip",
            {"pip": pip_requirements},
        ],
    }
    header = (
        "# conda environment for this project. Python comes from conda-forge;\n"
        "# everything else installs through pip so the dependency list stays\n"
        "# single-sourced in pyproject.toml.\n"
        "#\n"
        f"#   conda env create -f environment.yml\n"
        f"#   conda activate {answers.repo_name}\n"
    )
    (root / "environment.yml").write_text(
        header + yaml.safe_dump(document, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    return [
        f"environment.yml        conda env {answers.repo_name}, python {answers.python_version}"
    ]


# --- venv + pip -------------------------------------------------------------


def write_requirements(answers: ProjectAnswers, root: Path) -> list[str]:
    deps = read_dependencies(root)
    runtime = [*deps.runtime, *_selected_extra_requirements(answers, deps)]

    runtime_header = (
        "# Runtime dependencies, generated from [project.dependencies] in\n"
        "# pyproject.toml plus the extras this project selected. Regenerate by\n"
        "# re-running the setup wizard, or edit pyproject.toml and mirror it here.\n"
    )
    dev_header = (
        "# Development dependencies. Installing this file installs the runtime\n"
        "# set too, so one command is enough:\n"
        "#\n"
        "#   python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt\n"
        "\n"
        "-r requirements.txt\n"
    )

    (root / "requirements.txt").write_text(
        runtime_header + "\n".join(runtime) + "\n", encoding="utf-8"
    )
    (root / "requirements-dev.txt").write_text(
        dev_header + "\n".join(deps.dev) + "\n", encoding="utf-8"
    )
    return ["requirements.txt       runtime and dev dependency lists"]


def write_manifest(answers: ProjectAnswers, root: Path) -> list[str]:
    """Whichever manifest the chosen manager needs, or none for uv."""
    writers = {"pixi": write_pixi, "conda": write_conda, "venv+pip": write_requirements}
    writer = writers.get(answers.environment_manager)
    return writer(answers, root) if writer else []
