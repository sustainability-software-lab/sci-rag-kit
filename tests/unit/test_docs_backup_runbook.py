"""The backup runbook, executed rather than read.

F-006 in the 2026-08-29 documentation route audit: the local backup procedure
ran `pg_dump "$SCI_RAG_DATABASE_URL_SYNC"`, but no setting, environment
example, helper, or earlier instruction ever defines that name. In a normal
shell it expanded to an empty first argument; under `bash -u` it aborted
before `pg_dump` could run.

A backup procedure is only correct if it runs, so these tests run it. The
documented commands are extracted from the page, a stub `pg_dump` on `PATH`
records what it was actually handed, and the assertions are about that
recording. Nothing here opens a socket or contacts a database.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
OPERATIONS = ROOT / "docs" / "operations.md"

LOCAL_BACKUP_HEADING = "### Local or self-hosted Postgres"

# What a workspace .env looks like. The password lives in a passfile, which is
# what the Cloud SQL helper writes, so a correct procedure never has to put one
# on a command line.
FIXTURE_ENV = (
    "# sci-rag-kit configuration\n"
    "SCI_RAG_DATABASE_URL=postgresql+asyncpg://sci_rag@127.0.0.1:55070/sci_rag_demo"
    "?passfile=%2Ftmp%2Fpgpass\n"
    "SCI_RAG_EMBEDDING_PROVIDER=local-hash\n"
)

STUB_PG_DUMP = '#!/bin/sh\nprintf "ARG1=[%s]\\n" "$1"\n'


def _section(heading: str) -> str:
    text = OPERATIONS.read_text(encoding="utf-8")
    after = text.partition(heading)[2]
    assert after, f"{OPERATIONS.name} no longer has the section {heading!r}"
    return after.partition("\n### ")[0].partition("\n## ")[0]


def _first_bash_block(section: str) -> str:
    match = re.search(r"^```bash\n(.*?)^```", section, re.DOTALL | re.MULTILINE)
    assert match, "the section no longer contains a bash block"
    return match.group(1)


def _run(script: str, workdir: Path, *, shell: str = "sh") -> subprocess.CompletedProcess[str]:
    """Run a documented snippet with a stub pg_dump ahead of any real one."""
    stub_dir = workdir / "stub-bin"
    stub_dir.mkdir(exist_ok=True)
    stub = stub_dir / "pg_dump"
    stub.write_text(STUB_PG_DUMP, encoding="utf-8")
    stub.chmod(0o755)

    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("SCI_RAG_DATABASE_URL")
    }
    environment["PATH"] = f"{stub_dir}:{environment.get('PATH', '')}"
    return subprocess.run(
        [shell, "-c", script],
        cwd=workdir,
        env=environment,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / ".env").write_text(FIXTURE_ENV, encoding="utf-8")
    return tmp_path


def _recorded_argument(result: subprocess.CompletedProcess[str]) -> str:
    match = re.search(r"ARG1=\[(.*)\]", result.stdout)
    assert match, f"pg_dump was never reached. stdout={result.stdout!r} stderr={result.stderr!r}"
    return match.group(1)


def test_the_documented_backup_hands_pg_dump_a_real_connection_string(project: Path) -> None:
    script = _first_bash_block(_section(LOCAL_BACKUP_HEADING))
    result = _run(script, project)

    argument = _recorded_argument(result)
    assert argument, "pg_dump received an empty first argument"
    assert argument.startswith("postgresql://"), (
        f"pg_dump needs a libpq connection string, got {argument!r}"
    )
    assert "+asyncpg" not in argument, "libpq does not understand the asyncpg driver marker"


def test_the_documented_backup_survives_unset_variable_checking(project: Path) -> None:
    """`bash -u` is a normal thing for a careful operator to have on."""
    script = _first_bash_block(_section(LOCAL_BACKUP_HEADING))
    result = _run("set -u\n" + script, project, shell="bash")

    assert "unbound variable" not in result.stderr, result.stderr
    assert _recorded_argument(result), "pg_dump received an empty first argument under set -u"


def test_the_procedure_keeps_the_password_off_the_command_line(project: Path) -> None:
    """A connection string that carries a passfile never has to carry a secret."""
    script = _first_bash_block(_section(LOCAL_BACKUP_HEADING))
    argument = _recorded_argument(_run(script, project))

    assert "passfile" in argument, "the derived URL dropped the passfile reference"
    # A libpq URL with a password looks like scheme://user:password@host.
    assert not re.match(r"^postgresql://[^/@]*:[^/@]*@", argument), (
        f"the procedure put a password on the command line: {argument!r}"
    )


def test_every_name_the_procedure_uses_is_defined_before_it_is_used() -> None:
    """The defect was a name nothing in the repository ever sets."""
    script = _first_bash_block(_section(LOCAL_BACKUP_HEADING))
    used = set(re.findall(r'"\$\{?([A-Z_][A-Z0-9_]*)\}?"', script))
    assigned = set(re.findall(r"^([A-Z_][A-Z0-9_]*)=", script, re.MULTILINE))

    undefined = sorted(used - assigned)
    assert undefined == [], (
        f"the backup snippet reads {undefined} without defining them, and nothing "
        "in the repository exports them"
    )
