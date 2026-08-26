"""The corpus manifest: one line of JSON per document.

A manifest is how you tell the kit what you know about your documents:
where the file lives, who wrote it, when, under what license. Everything
except ``path`` is optional; the kit does something sensible with whatever
you provide. You can also skip the manifest entirely and point ``ingest``
at a folder, which auto-builds an entry per supported file.

Example line::

    {"path": "data/raw/fresno_2023.pdf", "title": "Fresno County Crop Report 2023",
     "authors": ["Fresno County Dept. of Agriculture"], "year": 2023,
     "license_class": "public", "source": "county_ag_reports"}
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from sci_rag.ingest.parsers import SUPPORTED_SUFFIXES
from sci_rag.licensing import normalize_license_class


class CorpusEntry(BaseModel):
    path: Path
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    url: str | None = None
    license_class: str = "unknown"
    source: str = "local"

    @field_validator("license_class", mode="before")
    @classmethod
    def _normalize_license(cls, value: str | None) -> str:
        return normalize_license_class(value)


def load_manifest(manifest_path: Path) -> list[CorpusEntry]:
    """Read a JSONL manifest. Paths are resolved relative to the manifest file."""
    entries: list[CorpusEntry] = []
    base = manifest_path.parent
    for line_number, line in enumerate(
        manifest_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{manifest_path.name} line {line_number} is not valid JSON: {exc}"
            ) from exc
        entry = CorpusEntry.model_validate(data)
        if not entry.path.is_absolute():
            entry.path = (base / entry.path).resolve()
        entries.append(entry)
    return entries


def discover_folder(folder: Path, *, source: str = "local") -> list[CorpusEntry]:
    """Build manifest entries for every supported file under a folder."""
    entries = [
        CorpusEntry(path=path.resolve(), source=source)
        for path in sorted(folder.rglob("*"))
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    ]
    return entries
