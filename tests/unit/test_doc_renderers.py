from pathlib import Path
from runpy import run_path


def _renderer(path: str, name: str):  # type: ignore[no-untyped-def]
    return run_path(path)[name]


def test_cli_reference_walks_top_level_and_nested_commands() -> None:
    render_cli_docs = _renderer("scripts/render_cli_docs.py", "render_cli_docs")
    page = render_cli_docs()

    assert "| `sci-rag ingest` |" in page
    assert "| `sci-rag db upgrade` |" in page
    assert "| `sci-rag eval calibrate` |" in page
    assert "| `sci-rag corpus snapshot` |" in page
    assert "| `sci-rag corpus enrich` |" in page
    assert "| `sci-rag campaign discover` |" in page
    assert "| `sci-rag campaign build` |" in page
    assert "`--include-retracted`" in page
    assert page.count("\n## `sci-rag ") >= 20


def test_configuration_reference_matches_complete_env_example() -> None:
    render_config_docs = _renderer("scripts/render_config_docs.py", "render_config_docs")
    page = render_config_docs(Path(".env.example"))

    assert "`SCI_RAG_DATABASE_URL`" in page
    assert "`SCI_RAG_EXTRACTION_MODEL`" in page
    assert "`SCI_RAG_CORS_ORIGINS`" in page
    assert "`retrieval.reranker.timeout_s`" in page
