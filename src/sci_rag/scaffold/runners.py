"""One profile per environment manager.

The kit is wired to a dependency manager in five places: the Makefile, the CI
workflow, the Dockerfile, the dev container, and every command in the docs. If
those five disagree the generated project is broken on its first run, so they
are all rendered from a single :class:`RunnerProfile`. Nothing else in the
scaffold may hardcode a manager's name.

Only ``uv`` ships today, which is what the template itself uses. Adding pixi,
conda, or venv+pip is a new entry here, not a redesign.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RunnerProfile:
    """Everything manager-specific about a generated project.

    ``run_prefix`` is empty for managers that expect an already-activated
    environment, so always build commands with :meth:`run` rather than by
    concatenating; otherwise those projects get a stray leading space in
    every Makefile recipe.
    """

    key: str
    label: str
    run_prefix: str
    sync_command: str
    manifest: str
    lockfile: str | None
    ci_setup_action: str

    def run(self, command: str) -> str:
        return f"{self.run_prefix} {command}".strip()


PROFILES: dict[str, RunnerProfile] = {
    "uv": RunnerProfile(
        key="uv",
        label="uv",
        run_prefix="uv run",
        sync_command="uv sync",
        manifest="pyproject.toml",
        lockfile="uv.lock",
        ci_setup_action="astral-sh/setup-uv@v7",
    ),
}


def runner_keys() -> list[str]:
    return list(PROFILES)


def get_runner(key: str) -> RunnerProfile:
    try:
        return PROFILES[key]
    except KeyError:
        raise KeyError(
            f"Unknown environment manager {key!r}. Known: {', '.join(PROFILES)}."
        ) from None
