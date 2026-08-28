"""Getting the template onto disk before the appliers run.

`sci-rag-new` starts in a parent directory with nothing checked out, so it has
to fetch the real repository at a pinned tag. Everything here runs offline: the
network path is exercised against a stub transport rather than GitHub.
"""

from __future__ import annotations

import io
import re
import tarfile
from pathlib import Path

import httpx
import pytest

from sci_rag.scaffold.fetch import (
    TemplateFetchError,
    fetch_template,
    tarball_url,
    template_ref,
)


def _tarball(*, top: str = "sci-rag-kit-0.2.0") -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, body in (
            ("pyproject.toml", b'[project]\nname = "sci-rag-kit"\n'),
            ("domain/domain.yaml", b'name: "Demo"\n'),
        ):
            info = tarfile.TarInfo(f"{top}/{name}")
            info.size = len(body)
            archive.addfile(info, io.BytesIO(body))
    return buffer.getvalue()


def _client(payload: bytes, *, status: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=payload)

    return httpx.Client(transport=httpx.MockTransport(handler))


# --- ref and url ------------------------------------------------------------


def test_the_default_ref_is_the_installed_version() -> None:
    assert template_ref(version="0.2.0") == "v0.2.0"


def test_the_installed_version_is_used_when_none_is_given() -> None:
    """A given generator release always produces the same project."""
    assert template_ref().startswith("v")


def test_the_url_points_at_the_tag() -> None:
    assert tarball_url("v0.2.0").endswith("/tar.gz/refs/tags/v0.2.0")


def test_a_branch_ref_resolves_to_a_head_url() -> None:
    assert tarball_url("main").endswith("/tar.gz/refs/heads/main")


# --- local checkout ---------------------------------------------------------


def test_a_local_checkout_is_copied(tmp_path: Path) -> None:
    source = tmp_path / "checkout"
    (source / "domain").mkdir(parents=True)
    (source / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (source / "domain" / "domain.yaml").write_text("name: x\n", encoding="utf-8")
    target = tmp_path / "new-project"

    described = fetch_template(target, template_path=source)

    assert (target / "pyproject.toml").exists()
    assert (target / "domain" / "domain.yaml").exists()
    assert str(source) in described


def test_a_local_checkout_copy_leaves_out_git_and_build_state(tmp_path: Path) -> None:
    source = tmp_path / "checkout"
    (source / ".git").mkdir(parents=True)
    (source / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (source / ".venv").mkdir()
    (source / ".venv" / "pyvenv.cfg").write_text("home = /usr\n", encoding="utf-8")
    (source / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    target = tmp_path / "new-project"

    fetch_template(target, template_path=source)

    assert not (target / ".git").exists()
    assert not (target / ".venv").exists()


def test_a_missing_local_checkout_is_reported(tmp_path: Path) -> None:
    with pytest.raises(TemplateFetchError, match="nowhere"):
        fetch_template(tmp_path / "out", template_path=tmp_path / "nowhere")


# --- network ----------------------------------------------------------------


def test_the_tarball_is_extracted_with_its_top_level_directory_stripped(tmp_path: Path) -> None:
    target = tmp_path / "new-project"

    fetch_template(target, ref="v0.2.0", client=_client(_tarball()))

    assert (target / "pyproject.toml").exists()
    assert (target / "domain" / "domain.yaml").exists()
    assert not (target / "sci-rag-kit-0.2.0").exists()


def test_a_missing_tag_says_which_tag(tmp_path: Path) -> None:
    with pytest.raises(TemplateFetchError, match=re.escape("v9.9.9")):
        fetch_template(tmp_path / "out", ref="v9.9.9", client=_client(b"", status=404))


def test_a_corrupt_tarball_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(TemplateFetchError, match="archive"):
        fetch_template(tmp_path / "out", ref="v0.2.0", client=_client(b"not a tarball"))


def test_a_path_traversing_member_is_refused(tmp_path: Path) -> None:
    """Model the hostile-archive case explicitly rather than trusting the default."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        info = tarfile.TarInfo("sci-rag-kit-0.2.0/../../escaped.txt")
        info.size = 3
        archive.addfile(info, io.BytesIO(b"bad"))
    with pytest.raises(TemplateFetchError):
        fetch_template(tmp_path / "out", ref="v0.2.0", client=_client(buffer.getvalue()))
    assert not (tmp_path / "escaped.txt").exists()


# --- target directory -------------------------------------------------------


def test_a_non_empty_target_is_refused(tmp_path: Path) -> None:
    target = tmp_path / "new-project"
    target.mkdir()
    (target / "something.txt").write_text("mine\n", encoding="utf-8")

    with pytest.raises(TemplateFetchError, match="not empty"):
        fetch_template(target, ref="v0.2.0", client=_client(_tarball()))

    assert (target / "something.txt").read_text(encoding="utf-8") == "mine\n"


def test_an_empty_target_directory_is_fine(tmp_path: Path) -> None:
    target = tmp_path / "new-project"
    target.mkdir()
    fetch_template(target, ref="v0.2.0", client=_client(_tarball()))
    assert (target / "pyproject.toml").exists()
