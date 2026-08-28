"""The generated-project matrix has to gate on its own diagnosis.

`doctor` was demoted to `continue-on-error` while it reported FAIL for an
offline project. Once that is fixed the demotion is a hole: a generated
project could regress into an unhealthy state and the matrix would still be
green. This test keeps the gate from quietly slipping back.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "generated-projects.yml"


def _doctor_step() -> dict[str, Any]:
    workflow = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    steps = workflow["jobs"]["generate"]["steps"]
    matches = [step for step in steps if "sci-rag doctor" in step.get("run", "")]
    assert len(matches) == 1, f"expected exactly one doctor step, found {len(matches)}"
    return matches[0]


def test_the_generated_project_matrix_gates_on_doctor() -> None:
    step = _doctor_step()

    assert "continue-on-error" not in step
    assert "if" not in step, "an always() or conditional guard would soften the gate"
