"""The Docker-free database reaches exactly the managers that can offer it.

conda-forge ships the PostgreSQL server and the pgvector extension as
ordinary packages, so pixi and conda projects can run the database without a
container runtime. PyPI ships neither, so uv and venv+pip projects cannot,
and a generated project must not advertise a path its own manager cannot
take. One capability on the runner profile decides that for every surface.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from sci_rag.scaffold import apply
from sci_rag.scaffold.answers import ProjectAnswers
from sci_rag.scaffold.questions import default_answers
from sci_rag.scaffold.runners import PROFILES, get_runner, runner_keys

REPO_ROOT = Path(__file__).parents[2]
SLUG = "membrane-materials-kb"

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

_LOCAL_DB = "scripts/local_postgres.py"
_CLOUD_DB = "scripts/cloud_postgres.py"


def _generate(tmp_path: Path, manager: str, *, include_cloud: str = "No") -> Path:
    root = tmp_path / "template"
    root.mkdir(parents=True)
    for name in _COPY_FILES:
        shutil.copy(REPO_ROOT / name, root / name)
    for tree in _COPY_TREES:
        shutil.copytree(REPO_ROOT / tree, root / tree, ignore=shutil.ignore_patterns("__pycache__"))
    (root / "infra" / "terraform").mkdir(parents=True)
    (root / "infra" / "terraform" / "main.tf").write_text("# terraform\n", encoding="utf-8")
    shutil.copytree(
        REPO_ROOT / "infra" / "terraform" / "dev-database",
        root / "infra" / "terraform" / "dev-database",
    )
    (root / "data" / "demo").mkdir(parents=True)
    (root / "data" / "demo" / "manifest.jsonl").write_text("{}\n", encoding="utf-8")
    (root / "examples").mkdir()
    (root / "examples" / "library_quickstart.py").write_text("# example\n", encoding="utf-8")

    raw = dict(default_answers())
    raw.update(
        {
            "project_name": "Membrane Materials KB",
            "repo_name": SLUG,
            "environment_manager": manager,
            "include_cloud_database": include_cloud,
            "initialize_git": "No",
        }
    )
    apply.apply_all(ProjectAnswers.from_raw(raw), root, year=2026)
    return root


# --- the capability ---------------------------------------------------------


def test_only_the_conda_forge_managers_offer_a_local_database() -> None:
    offering = {key for key, profile in PROFILES.items() if profile.offers_local_postgres}

    assert offering == {"pixi", "conda"}


@pytest.mark.parametrize("manager", ["pixi", "conda"])
def test_the_offering_managers_name_both_packages(manager: str) -> None:
    packages = get_runner(manager).conda_forge_packages

    assert [name for name, _ in packages] == ["postgresql", "pgvector"]


def test_the_postgresql_bound_is_the_tested_range() -> None:
    """ADR 0008 supports 16 through 18; the manifests have to say the same."""
    packages = dict(get_runner("pixi").conda_forge_packages)

    assert packages["postgresql"] == ">=16,<19"


# --- the generated manifests ------------------------------------------------


def test_a_pixi_project_gets_the_server_in_its_manifest(tmp_path: Path) -> None:
    root = _generate(tmp_path, "pixi")

    manifest = (root / "pyproject.toml").read_text(encoding="utf-8")

    assert 'postgresql = ">=16,<19"' in manifest
    assert "pgvector = " in manifest


def test_a_conda_project_gets_the_server_in_its_environment_file(tmp_path: Path) -> None:
    root = _generate(tmp_path, "conda")

    document = yaml.safe_load((root / "environment.yml").read_text(encoding="utf-8"))
    named = [d for d in document["dependencies"] if isinstance(d, str)]

    assert "postgresql>=16,<19" in named
    assert any(d.startswith("pgvector") for d in named)


@pytest.mark.parametrize("manager", ["uv", "venv+pip"])
def test_the_pypi_managers_bundle_no_server_but_allow_a_system_one(
    tmp_path: Path, manager: str
) -> None:
    """PyPI has no server package, but Postgres.app can still drive the helper."""
    root = _generate(tmp_path, manager)

    for name in ("pyproject.toml", "Makefile", "requirements.txt"):
        path = root / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        assert "postgresql>=16" not in text
    makefile = (root / "Makefile").read_text(encoding="utf-8")
    run = get_runner(manager).run("python scripts/local_postgres.py", project_slug=SLUG)
    assert f"{run} start" in makefile
    assert "SCI_RAG_DB_BACKEND ?= docker" in makefile


# --- the generated task commands --------------------------------------------


@pytest.mark.parametrize("manager", ["pixi", "conda"])
def test_the_offering_managers_bring_up_the_database_without_docker(
    tmp_path: Path, manager: str
) -> None:
    root = _generate(tmp_path, manager)

    makefile = (root / "Makefile").read_text(encoding="utf-8")

    assert "docker compose up -d --wait" not in makefile
    assert "docker compose down" not in makefile
    assert _LOCAL_DB in makefile


@pytest.mark.parametrize("manager", ["uv", "venv+pip"])
def test_the_pypi_managers_keep_the_compose_database(tmp_path: Path, manager: str) -> None:
    root = _generate(tmp_path, manager)

    makefile = (root / "Makefile").read_text(encoding="utf-8")

    assert "docker compose up -d --wait" in makefile


def test_the_local_database_script_survives_generation(tmp_path: Path) -> None:
    """Every manager keeps the script; only two wire their Makefile to it."""
    for manager in runner_keys():
        root = _generate(tmp_path / manager, manager)
        assert (root / "scripts" / "local_postgres.py").exists()


@pytest.mark.parametrize("manager", runner_keys())
def test_cloud_database_assets_are_pruned_by_default(tmp_path: Path, manager: str) -> None:
    root = _generate(tmp_path / manager, manager)

    assert not (root / _CLOUD_DB).exists()
    assert not (root / "infra" / "terraform" / "dev-database").exists()
    assert _CLOUD_DB not in (root / "Makefile").read_text(encoding="utf-8")


@pytest.mark.parametrize("manager", runner_keys())
def test_every_manager_can_keep_the_cloud_database_assets(tmp_path: Path, manager: str) -> None:
    root = _generate(tmp_path / manager, manager, include_cloud="Yes")

    assert (root / _CLOUD_DB).exists()
    assert (root / "infra" / "terraform" / "dev-database").exists()
    makefile = (root / "Makefile").read_text(encoding="utf-8")
    command = get_runner(manager).run("python scripts/cloud_postgres.py", project_slug=SLUG)
    assert f"{command} start" in makefile
    assert f"{command} stop" in makefile


def test_template_preserves_the_literal_compose_rewrite_seam() -> None:
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    assert "SCI_RAG_DB_BACKEND ?= docker" in makefile
    assert "docker compose up -d --wait" in makefile
    assert "docker compose down" in makefile


def test_cloud_helper_contains_no_environment_manager_commands() -> None:
    script = (REPO_ROOT / _CLOUD_DB).read_text(encoding="utf-8")

    for profile in PROFILES.values():
        for token in profile.command_tokens():
            assert token not in script


def test_the_data_directory_is_ignored() -> None:
    """A cluster under the project root is a corpus waiting to be committed."""
    ignored = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert ".pgdata/" in ignored
    assert ".pgdata.log" in ignored
    assert ".cloudsql/" in ignored
