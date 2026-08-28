"""Evaluation CLI commands keep one async engine on one event loop."""

from __future__ import annotations

import asyncio
from pathlib import Path

from typer.testing import CliRunner

from sci_rag.cli.main import app


def test_resolved_entities_audit_and_retrieval_share_one_event_loop(
    monkeypatch, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    class LoopBoundSession:
        async def __aenter__(self):  # type: ignore[no-untyped-def]
            loop = asyncio.get_running_loop()
            if factory.loop is None:
                factory.loop = loop
            elif factory.loop is not loop:
                raise RuntimeError("Event loop is closed")
            return self

        async def __aexit__(self, *args):  # type: ignore[no-untyped-def]
            return None

        async def scalar(self, _statement):  # type: ignore[no-untyped-def]
            return 1

    class LoopBoundFactory:
        loop: asyncio.AbstractEventLoop | None = None

        def __call__(self) -> LoopBoundSession:
            return LoopBoundSession()

    factory = LoopBoundFactory()

    async def fake_run_retrieval_eval(*args, **kwargs):  # type: ignore[no-untyped-def]
        return []

    async def fake_fingerprint(session_factory):  # type: ignore[no-untyped-def]
        async with session_factory():
            return {"documents": 0, "chunks": 0}

    def fake_write_report(**kwargs):  # type: ignore[no-untyped-def]
        return tmp_path / "report.json", tmp_path / "report.md"

    import sci_rag.db
    import sci_rag.evals
    import sci_rag.evals.report
    import sci_rag.retrieve

    monkeypatch.setattr(sci_rag.db, "get_session_factory", lambda: factory)
    monkeypatch.setattr(sci_rag.evals, "run_retrieval_eval", fake_run_retrieval_eval)
    monkeypatch.setattr(sci_rag.evals.report, "corpus_fingerprint", fake_fingerprint)
    monkeypatch.setattr(sci_rag.evals.report, "write_report", fake_write_report)
    monkeypatch.setattr(sci_rag.retrieve, "Retriever", lambda: object())

    result = CliRunner().invoke(
        app,
        [
            "eval",
            "retrieval",
            "--condition",
            "resolved_entities",
            "--snapshot",
            "resolved-test",
        ],
    )

    assert result.exit_code == 0, result.exception
    assert "Report written" in result.output
