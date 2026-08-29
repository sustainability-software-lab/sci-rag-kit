"""What a builder is allowed to see.

`docker build .` and `gcloud builds submit .` both hand a directory to a
builder. A checkout is not that directory: it also holds credentials under
`.cloudsql/`, agent working files under `.context/`, a filled in `.env`, a
local PostgreSQL cluster under `.pgdata/`, Terraform state that contains a
generated database password, and whatever corpus was last ingested under
`data/raw/`. F-027 in the 2026-08-29 documentation route audit proved all
four classes crossed: a synthetic `COPY .` stage admitted them, and
`gcloud meta list-files-for-upload` listed `.context/sentinel.txt`.

`.dockerignore` and `.gcloudignore` answer that, and they answer it fail
closed: exclude everything, then re-admit exactly the documented build
inputs. These tests hold that shape in place. They check the manifests
rather than a live build because Docker and gcloud are not available in the
Python test job; the `docker` CI job runs the real `COPY .` proof against
Docker's own context resolution.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCKERIGNORE = ROOT / ".dockerignore"
GCLOUDIGNORE = ROOT / ".gcloudignore"
DOCKERFILE = ROOT / "Dockerfile"

# The exclude-everything line each manifest has to open with. Docker matches
# top-level names, gcloud uses gitignore syntax and anchors with a slash.
_EXCLUDE_ALL = {".dockerignore": "*", ".gcloudignore": "/*"}

# Local state that must never reach a builder. Every entry is a real class
# named in the audit or in .gitignore, not a hypothetical.
SENSITIVE_PATHS = (
    ".env",
    ".cloudsql/password",
    ".cloudsql/pgpass",
    ".context/sentinel.txt",
    ".pgdata/postgresql.conf",
    ".venv/pyvenv.cfg",
    "data/raw/private.pdf",
    "data/interim/staged.jsonl",
    "data/processed/chunks.jsonl",
    "eval_results/run-1/report.json",
    "infra/terraform/terraform.tfstate",
    "infra/terraform/terraform.tfvars",
    ".pytest_cache/CACHEDIR.TAG",
    ".mypy_cache/cache.db",
    ".ruff_cache/content",
    "site/index.html",
    ".git/config",
)

# What the image documents as its runtime inputs.
RUNTIME_INPUTS = (
    "pyproject.toml",
    "uv.lock",
    "README.md",
    "alembic.ini",
    "src/sci_rag/__init__.py",
    "domain/domain.yaml",
    "migrations/env.py",
)


def _manifest(path: Path) -> tuple[str, list[str]]:
    """Split a manifest into its exclude-all line and its allowlist."""
    lines = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert lines, f"{path.name} has no patterns"
    return lines[0], [line.lstrip("!").strip("/") for line in lines[1:]]


def _admits(path: Path, candidate: str) -> bool:
    """Whether ``candidate``, a repository-relative path, survives the manifest.

    Both manifests exclude every top-level entry and then re-admit whole
    entries by name, so admission is decided by the first path segment. The
    form test below is what keeps that simplification true.
    """
    _, allowed = _manifest(path)
    return candidate.split("/", 1)[0] in allowed


@pytest.mark.parametrize("manifest", [DOCKERIGNORE, GCLOUDIGNORE], ids=lambda p: p.name)
def test_the_manifest_exists(manifest: Path) -> None:
    """Without the file, gcloud falls back to .gitignore and Docker to nothing."""
    assert manifest.is_file(), f"{manifest.name} is missing, so the build context is unbounded"


@pytest.mark.parametrize("manifest", [DOCKERIGNORE, GCLOUDIGNORE], ids=lambda p: p.name)
def test_the_manifest_is_an_allowlist_not_a_denylist(manifest: Path) -> None:
    """A denylist fails open. This is the shape the whole fix depends on."""
    first, _ = _manifest(manifest)
    assert first == _EXCLUDE_ALL[manifest.name], (
        f"{manifest.name} must open by excluding everything, found {first!r}"
    )
    rest = [
        line.strip()
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ][1:]
    offenders = [line for line in rest if not line.startswith("!")]
    assert offenders == [], (
        f"{manifest.name} must only re-admit after the exclude-all line: {offenders}"
    )


@pytest.mark.parametrize("manifest", [DOCKERIGNORE, GCLOUDIGNORE], ids=lambda p: p.name)
@pytest.mark.parametrize("sensitive", SENSITIVE_PATHS)
def test_local_state_never_reaches_a_builder(manifest: Path, sensitive: str) -> None:
    assert not _admits(manifest, sensitive), (
        f"{manifest.name} admits {sensitive} into the build context"
    )


@pytest.mark.parametrize("manifest", [DOCKERIGNORE, GCLOUDIGNORE], ids=lambda p: p.name)
@pytest.mark.parametrize("runtime_input", RUNTIME_INPUTS)
def test_the_documented_runtime_inputs_still_reach_the_builder(
    manifest: Path, runtime_input: str
) -> None:
    """Fail closed is only correct if the image still builds."""
    assert _admits(manifest, runtime_input), (
        f"{manifest.name} excludes {runtime_input}, which the image needs"
    )


def _dockerfile_context_sources() -> list[str]:
    """The paths the Dockerfile copies out of the build context.

    ``COPY --from=<stage>`` reads from an earlier stage rather than from the
    context, so it is not a context source.
    """
    sources: list[str] = []
    for line in DOCKERFILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.upper().startswith("COPY "):
            continue
        parts = stripped.split()[1:]
        if any(part.startswith("--from=") for part in parts):
            continue
        parts = [part for part in parts if not part.startswith("--")]
        sources.extend(parts[:-1])
    return sources


def test_every_dockerfile_copy_source_is_admitted() -> None:
    """A COPY of an excluded path builds a quietly incomplete image.

    This is the test that catches the next person who adds a COPY without
    adding its source to the manifests.
    """
    sources = _dockerfile_context_sources()
    assert sources, "no context COPY sources found; the Dockerfile parse is wrong"
    for manifest in (DOCKERIGNORE, GCLOUDIGNORE):
        missing = [source for source in sources if not _admits(manifest, source)]
        assert missing == [], f"{manifest.name} excludes Dockerfile COPY sources: {missing}"


def test_both_manifests_admit_exactly_the_same_set() -> None:
    """A local build and a Cloud Build submission must see the same directory.

    If they diverge, an image that builds on a laptop can fail in Cloud Build
    for a reason nobody can see from either file alone.
    """
    _, docker_allowed = _manifest(DOCKERIGNORE)
    _, gcloud_allowed = _manifest(GCLOUDIGNORE)
    assert sorted(docker_allowed) == sorted(gcloud_allowed)


def test_the_build_definition_is_uploaded_with_the_source() -> None:
    """`gcloud builds submit` has to upload the Dockerfile or the build has none.

    `.dockerignore` admits the same two files for symmetry, though Docker
    itself never copies either one into an image: it excludes them from
    every `COPY` regardless of what the manifest says.
    """
    for manifest in (DOCKERIGNORE, GCLOUDIGNORE):
        assert _admits(manifest, "Dockerfile")
        assert _admits(manifest, ".dockerignore")


def test_the_deployment_guide_warns_about_admitted_paths() -> None:
    """A reader putting a private corpus in src/ deserves to be told."""
    guide = (ROOT / "docs" / "deploy-gcp.md").read_text(encoding="utf-8")
    assert ".gcloudignore" in guide
    assert ".dockerignore" in guide
    assert re.search(r"upload|build context", guide, re.IGNORECASE)
