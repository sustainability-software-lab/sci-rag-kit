from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar

from typer.testing import CliRunner

from sci_rag.campaigns import http as campaign_http
from sci_rag.cli.main import app

FIXTURES = Path(__file__).parents[1] / "fixtures" / "campaigns"
runner = CliRunner()


class StubPoliteClient:
    init_kwargs: ClassVar[dict[str, Any]] = {}

    def __init__(self, **kwargs: Any) -> None:
        type(self).init_kwargs = kwargs

    async def __aenter__(self) -> StubPoliteClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def get_json(
        self, _url: str, *, params: dict[str, str | int] | None = None
    ) -> dict[str, Any]:
        return json.loads((FIXTURES / "crossref_work.json").read_text(encoding="utf-8"))


def test_campaign_discover_doi_file_prints_deduplicated_list_and_writes_state(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(campaign_http, "PoliteHttpClient", StubPoliteClient)
    doi_file = tmp_path / "seeds.txt"
    doi_file.write_text(
        "10.7717/PEERJ.4375\nhttps://doi.org/10.7717/peerj.4375\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "campaign",
            "discover",
            "--doi-file",
            str(doi_file),
            "--name",
            "OA Seed",
            "--mailto",
            "researcher@example.org",
            "--campaign-root",
            str(tmp_path / "campaigns"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert result.output.count("10.7717/peerj.4375") == 1
    assert "1 discovered" in result.output
    assert "1 duplicate" in result.output
    assert (tmp_path / "campaigns" / "oa-seed" / "state.jsonl").exists()
    assert StubPoliteClient.init_kwargs["mailto"] == "researcher@example.org"


def test_campaign_discover_requires_exactly_one_input(tmp_path: Path) -> None:
    doi_file = tmp_path / "seeds.txt"
    doi_file.write_text("10.7717/peerj.4375\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "campaign",
            "discover",
            "--topic",
            "open access",
            "--doi-file",
            str(doi_file),
            "--mailto",
            "researcher@example.org",
        ],
    )

    assert result.exit_code != 0
    assert "exactly one" in result.output.lower()
