"""The published benchmark always starts from isolated database state."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))

import scripts.create_benchmark_database as benchmark_database
from scripts.create_benchmark_database import benchmark_database_urls


def test_benchmark_database_urls_preserve_connection_and_change_database() -> None:
    admin_url, benchmark_url = benchmark_database_urls(
        "postgresql+asyncpg://scientist:secret@localhost:5433/sci_rag",
        "sci_rag_benchmark_20260828_12345",
    )

    assert admin_url.database == "postgres"
    assert benchmark_url.database == "sci_rag_benchmark_20260828_12345"
    assert benchmark_url.username == "scientist"
    assert benchmark_url.password == "secret"
    assert benchmark_url.port == 5433


@pytest.mark.parametrize(
    "name",
    ["sci-rag-benchmark", "sci_rag;drop_database", "9starts_with_digit", "x" * 64],
)
def test_benchmark_database_name_must_be_a_safe_postgres_identifier(name: str) -> None:
    with pytest.raises(ValueError, match="database name"):
        benchmark_database_urls("postgresql+asyncpg://localhost/sci_rag", name)


def test_helper_passes_database_url_only_to_child_environment(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    secret_url = "postgresql+asyncpg://scientist:do-not-print@localhost/fresh"
    received: dict[str, object] = {}

    async def fake_create(_database_url: str, _name: str) -> str:
        return secret_url

    def fake_run(command, *, check, env):  # type: ignore[no-untyped-def]
        received.update(command=command, check=check, env=env)

    monkeypatch.setattr(benchmark_database, "create_benchmark_database", fake_create)
    monkeypatch.setattr(benchmark_database.subprocess, "run", fake_run)
    monkeypatch.setattr(
        "sci_rag.config.get_settings",
        lambda: SimpleNamespace(database_url="postgresql+asyncpg://localhost/source"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["create_benchmark_database.py", "--name", "sci_rag_benchmark_test", "--", "make"],
    )

    benchmark_database.main()

    captured = capsys.readouterr()
    assert secret_url not in captured.out
    assert secret_url not in captured.err
    assert received["command"] == ["make"]
    assert received["check"] is True
    assert received["env"]["SCI_RAG_DATABASE_URL"] == secret_url  # type: ignore[index]


def test_make_benchmark_runs_the_whole_pipeline_in_the_child_environment() -> None:
    makefile = (Path(__file__).parents[2] / "Makefile").read_text(encoding="utf-8")
    entrypoint, pipeline = makefile.split("benchmark-in-db:", maxsplit=1)

    assert "scripts/create_benchmark_database.py" in entrypoint
    assert "$(MAKE) --no-print-directory benchmark-in-db" in entrypoint
    assert "export SCI_RAG_DATABASE_URL" not in makefile
    assert "SCI_RAG_BENCHMARK_ISOLATED" in pipeline
    assert "scripts/seed_resolution_benchmark.py" in pipeline
