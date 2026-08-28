"""Putting the template on disk before the appliers run.

`sci-rag-new` starts in a parent directory with nothing checked out, so it has
to bring the template down first. It fetches the real repository at the tag
matching its own installed version, which is what makes a given generator
release always produce the same project.

There is no git binary requirement and no template rendering: this downloads a
tarball with httpx, which is already a direct dependency, and extracts it.
What comes out is the runnable repository, byte for byte. The appliers then
rewrite its configuration in place (see ADR 0004).
"""

from __future__ import annotations

import io
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    import httpx

TEMPLATE_REPO = "sustainability-software-lab/sci-rag-kit"

# Build state and history from a local checkout. A generated project gets its
# own git history, and copying a virtualenv would be both wrong and enormous.
_LOCAL_EXCLUDES = shutil.ignore_patterns(
    ".git",
    ".venv",
    ".pixi",
    "__pycache__",
    "*.pyc",
    "site",
    "eval_results",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
)


class TemplateFetchError(RuntimeError):
    """The template could not be put in place."""


def template_ref(*, version: str | None = None) -> str:
    """The git ref this generator produces projects from.

    Pinned to the generator's own version so that upgrading the generator is
    the only way to change what a generated project contains.
    """
    if version is None:
        from importlib.metadata import PackageNotFoundError
        from importlib.metadata import version as installed_version

        try:
            version = installed_version("sci-rag-kit")
        except PackageNotFoundError:  # pragma: no cover - only when run from a bare tree
            raise TemplateFetchError(
                "sci-rag-kit is not installed, so its version cannot be resolved. "
                "Pass --ref to name a tag, or --template-path to use a local checkout."
            ) from None
    return f"v{version}"


def tarball_url(ref: str, *, repo: str = TEMPLATE_REPO) -> str:
    """codeload serves tags and branches from different paths."""
    kind = "tags" if ref.startswith("v") else "heads"
    return f"https://codeload.github.com/{repo}/tar.gz/refs/{kind}/{ref}"


def _require_empty(target: Path) -> None:
    if target.exists() and any(target.iterdir()):
        raise TemplateFetchError(
            f"{target} is not empty. Choose a different project name, or move the "
            "existing directory out of the way."
        )


def _copy_local(source: Path, target: Path) -> str:
    if not source.is_dir():
        raise TemplateFetchError(f"No template checkout at {source}.")
    shutil.copytree(source, target, ignore=_LOCAL_EXCLUDES, dirs_exist_ok=True)
    return f"local checkout at {source}"


def _extract(archive_bytes: bytes, target: Path) -> None:
    """Extract the archive, stripping GitHub's top-level directory.

    ``filter="data"`` refuses absolute paths, parent traversal, links out of
    the tree, and device files. Extracting a downloaded archive without it is
    how a hostile tag writes outside the target directory.
    """
    with tempfile.TemporaryDirectory() as scratch:
        staged = Path(scratch) / "staged"
        try:
            with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
                archive.extractall(staged, filter="data")
        except (tarfile.TarError, OSError, ValueError) as exc:
            raise TemplateFetchError(f"The downloaded archive could not be read: {exc}") from exc

        roots = [path for path in staged.iterdir() if path.is_dir()]
        if len(roots) != 1:
            raise TemplateFetchError(
                f"Expected one top-level directory in the archive, found {len(roots)}."
            )
        target.mkdir(parents=True, exist_ok=True)
        shutil.copytree(roots[0], target, dirs_exist_ok=True)


def fetch_template(
    target: Path,
    *,
    ref: str | None = None,
    template_path: Path | None = None,
    repo: str = TEMPLATE_REPO,
    client: httpx.Client | None = None,
) -> str:
    """Put the template at ``target``. Returns a description of where it came from.

    ``template_path`` uses a local checkout, which is what the tests and any
    offline user need. Otherwise the tarball comes from GitHub at ``ref``,
    defaulting to the tag matching this generator's version.
    """
    _require_empty(target)

    if template_path is not None:
        return _copy_local(template_path.expanduser(), target)

    resolved = ref or template_ref()
    url = tarball_url(resolved, repo=repo)

    import httpx as _httpx

    owned = client is None
    http = client or _httpx.Client(follow_redirects=True, timeout=60.0)
    try:
        response = http.get(url)
        if response.status_code == 404:
            # A 404 here has two very different causes and codeload cannot
            # tell them apart: the tag does not exist, or the repository is
            # not readable anonymously. The second one looks like a broken
            # generator to every user who is not a collaborator, so name it.
            raise TemplateFetchError(
                f"Could not fetch the template at {resolved} ({url}). Either that tag "
                f"does not exist, or {repo} is not publicly readable. Pass --ref to "
                "name another tag, or --template-path to generate from a local checkout."
            )
        response.raise_for_status()
        payload = response.content
    except _httpx.HTTPError as exc:
        raise TemplateFetchError(f"Could not download {url}: {exc}") from exc
    finally:
        if owned:
            http.close()

    _extract(payload, target)
    return f"{repo} at {resolved}"
