"""What the generated-project matrix has to keep proving.

`doctor` was demoted to `continue-on-error` while it reported FAIL for an
offline project. Once that is fixed the demotion is a hole: a generated
project could regress into an unhealthy state and the matrix would still be
green. The Docker-free database has the same shape of risk in reverse, since
documenting a path the matrix does not exercise is how it rots. These tests
keep both from quietly slipping.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "generated-projects.yml"
DOCKER_FREE = ROOT / ".github" / "workflows" / "docker-free-postgres.yml"


def _generate_steps() -> list[dict[str, Any]]:
    workflow = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    steps: list[dict[str, Any]] = workflow["jobs"]["generate"]["steps"]
    return steps


def _doctor_step() -> dict[str, Any]:
    matches = [step for step in _generate_steps() if "sci-rag doctor" in step.get("run", "")]
    assert len(matches) == 1, f"expected exactly one doctor step, found {len(matches)}"
    return matches[0]


def test_the_generated_project_matrix_gates_on_doctor() -> None:
    step = _doctor_step()

    assert "continue-on-error" not in step
    assert "if" not in step, "an always() or conditional guard would soften the gate"


def test_the_matrix_stands_up_the_docker_free_database_for_pixi_and_conda() -> None:
    """Criterion: the Docker-free path is not advertised before it is tested."""
    steps = _generate_steps()
    matches = [s for s in steps if "local_postgres.py" in s.get("run", "")]

    assert matches, "no step brings up the generated project's own database"
    guards = " ".join(str(s.get("if", "")) for s in matches)
    assert "pixi" in guards and "conda" in guards, (
        "the Docker-free legs have to be the two managers whose channel ships a server"
    )


def test_the_docker_free_workflow_covers_both_required_platforms() -> None:
    """Criterion: passes the integration suite on osx-arm64 and linux-64.

    The matrix is a `fromJSON` expression, so the platform list lives in the
    selector's script rather than in the matrix block. Assert on where it is
    actually written, not on the indirection.
    """
    workflow = yaml.load(DOCKER_FREE.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)

    chooser = " ".join(step.get("run", "") for step in workflow["jobs"]["select"]["steps"])
    assert "ubuntu-latest" in chooser and "linux-64" in chooser
    assert "macos-latest" in chooser and "osx-arm64" in chooser

    job = workflow["jobs"]["integration"]
    assert "needs.select.outputs.platforms" in job["strategy"]["matrix"]["include"]

    runs = " ".join(step.get("run", "") for step in job["steps"])
    assert "local_postgres.py start" in runs
    assert "tests/integration" in runs and "tests/server" in runs
    assert "docker" not in runs.lower(), "a Docker-free job must not reach for Docker"


def test_the_docker_free_workflow_refuses_a_skipped_suite() -> None:
    """A skipped integration suite looks identical to a passing one."""
    workflow = yaml.load(DOCKER_FREE.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    runs = " ".join(step.get("run", "") for step in workflow["jobs"]["integration"]["steps"])

    assert "Postgres unavailable" in runs, "nothing detects the skip path"
