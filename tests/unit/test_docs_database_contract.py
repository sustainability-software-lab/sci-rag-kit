"""Contracts for the supported development database documentation.

The database backend is selected independently from the environment manager,
and generated projects can retain or prune the optional Cloud helper. These
guards keep the public setup path, the lifecycle safety boundary, and the
machine-local Conductor recipe aligned with those shipped seams.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _one_line(path: str) -> str:
    return re.sub(r"\s+", " ", _read(path))


def test_setup_starts_the_selected_backend_with_docker_as_the_template_default() -> None:
    for path in ("README.md", "docs/quickstart.md"):
        page = _one_line(path)
        assert "`make setup` starts the selected database backend" in page, path
        assert "Docker is the template default" in page, path
        assert "`make setup` starts the compose Postgres" not in page, path

    readme = _read("README.md")
    assert "[Run Postgres your way](docs/run-postgres.md)" in readme


def test_postgres_guide_publishes_the_backend_matrix_and_cloud_stages() -> None:
    page = _read("docs/run-postgres.md")
    normalized = re.sub(r"\s+", " ", page)

    for heading in (
        "## Recommended defaults",
        "## One-time Cloud SQL provisioning",
        "## Start a Cloud SQL workspace",
        "## Manage the Cloud SQL lifecycle",
        "## Use Cloud SQL in Conductor workspaces",
    ):
        assert heading in page

    for manager in ("uv", "pixi", "conda", "venv + pip"):
        assert manager in page
    for backend in ("Docker", "conda-forge", "system PostgreSQL", "Cloud SQL"):
        assert backend in page

    for name in (
        "SCI_RAG_CLOUD_PG_PROJECT",
        "SCI_RAG_CLOUD_PG_INSTANCE",
        "SCI_RAG_CLOUD_PG_REGION",
        "SCI_RAG_CLOUD_PG_DIR",
        "SCI_RAG_CLOUD_PG_PORT",
        "SCI_RAG_CLOUD_PG_WORKSPACE",
        "SCI_RAG_CLOUD_PG_USER",
    ):
        assert f"`{name}`" in page

    assert '-var "project_id=YOUR_PROJECT"' in page
    assert "Terraform state contains the generated database password" in normalized
    assert "first start can take several minutes" in normalized
    assert "not an authorization boundary" in normalized
    assert "must not hold the only copy of a valuable corpus" in normalized


def test_cloud_lifecycle_table_preserves_workspace_and_shared_boundaries() -> None:
    page = _read("docs/run-postgres.md")
    lifecycle = re.sub(
        r"\s+",
        " ",
        page.partition("## Manage the Cloud SQL lifecycle")[2].partition("## ")[0],
    ).casefold()

    for action in ("`config`", "`start`", "`status`", "`stop`", "`pause`", "`resume`"):
        assert action in lifecycle
    assert "stops only the current workspace proxy" in lifecycle
    assert "affects every workspace" in lifecycle
    assert "do not delete" in lifecycle


def test_conductor_recipe_is_explicitly_user_installed_and_machine_local() -> None:
    page = _read("docs/run-postgres.md")
    recipe = re.sub(
        r"\s+",
        " ",
        page.partition("## Use Cloud SQL in Conductor workspaces")[2].partition("## ")[0],
    )

    assert "user-installed" in recipe
    assert "machine-local" in recipe
    assert "Conductor root clone" in recipe
    assert ".conductor/settings.local.toml" in recipe
    assert ".conductor/setup-cloud-workspace.sh" in recipe
    assert ".conductor/run-cloud-tests.sh" in recipe
    assert "make db-down" in recipe
    assert "must not pause" in recipe
    assert "does not ship" in recipe
    assert "/Users/" not in recipe
    assert "tylerhuntington" not in recipe.casefold()


def test_cloud_troubleshooting_uses_dynamic_ports_and_start_resumes() -> None:
    page = _read("docs/troubleshooting.md")
    cloud = page.partition("### Cloud SQL")[2].partition("## ")[0]

    assert "dynamic port" in cloud
    assert "`start` resumes" in cloud
    assert "`resume` changes the instance activation policy" in cloud
    assert "run `resume`, then `start`" not in cloud


def test_database_decisions_and_benchmark_reproduction_show_current_contract() -> None:
    adr8 = _read("docs/adr/0008-supported-postgresql-versions.md")
    adr9 = _read("docs/adr/0009-cloud-dev-database.md")
    benchmark_generator = _read("scripts/render_benchmarks.py")
    benchmarks = _read("docs/benchmarks.md")
    makefile = _read("Makefile")

    assert "Partially superseded by [ADR 0009]" in adr8
    assert "Cloud SQL was 3.65 times slower" in adr9
    assert "## Reversal conditions" in adr9
    assert "## Revisit if" not in adr9
    assert "selected PostgreSQL backend" in benchmark_generator
    assert "selected PostgreSQL backend" in benchmarks
    assert "Needs the selected PostgreSQL backend" in makefile
