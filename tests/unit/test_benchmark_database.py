"""The published benchmark always starts from isolated database state."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))

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


def test_make_benchmark_exports_the_fresh_database_for_the_whole_pipeline() -> None:
    makefile = (Path(__file__).parents[2] / "Makefile").read_text(encoding="utf-8")
    target = makefile.split("benchmark: db-up", maxsplit=1)[1].split("clean-demo:", maxsplit=1)[0]

    assert "scripts/create_benchmark_database.py" in target
    assert "export SCI_RAG_DATABASE_URL" in target
    assert target.index("export SCI_RAG_DATABASE_URL") < target.index(
        "scripts/seed_resolution_benchmark.py"
    )
