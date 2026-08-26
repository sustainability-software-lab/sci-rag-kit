"""Shared types for the retrieval subsystem.

The design rule that matters most here: **scope precedes ranking**. A scope
(license allowlist, source allowlist, excluded documents) is applied inside
every layer's SQL, before ordering and limiting. Filtering after ranking
would let an out-of-scope row crowd an eligible one out of a bounded
candidate pool, and excluded content could silently shape results. And an
explicitly empty license scope means "return nothing", never "return
everything".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import ColumnElement

from sci_rag.db.models import Document

Kind = Literal["chunk", "community"]
Key = tuple[Kind, str]

STAGES = ("vector", "keyword", "graph", "community", "hyde")


@dataclass(frozen=True)
class RetrievalScope:
    """What a caller is allowed to see.

    ``None`` means unrestricted for that dimension; an empty license tuple
    means deny everything (fail closed).
    """

    license_classes: tuple[str, ...] | None = None
    sources: tuple[str, ...] | None = None
    exclude_document_ids: tuple[str, ...] = ()

    def denies_all(self) -> bool:
        return self.license_classes is not None and len(self.license_classes) == 0

    def is_unrestricted(self) -> bool:
        return (
            self.license_classes is None and self.sources is None and not self.exclude_document_ids
        )


def scope_conditions(scope: RetrievalScope) -> list[ColumnElement[bool]]:
    """SQL conditions implementing a scope, for queries joined to documents."""
    conditions: list[ColumnElement[bool]] = []
    if scope.license_classes is not None:
        conditions.append(Document.license_class.in_(scope.license_classes))
    if scope.sources is not None:
        conditions.append(Document.source.in_(scope.sources))
    if scope.exclude_document_ids:
        conditions.append(Document.id.not_in(scope.exclude_document_ids))
    return conditions


@dataclass
class StageTrace:
    """Operational metadata about one retrieval stage. Content-free by design:
    no query text, no chunk text, so traces are always safe to log."""

    stage: str
    status: str  # "success" | "empty" | "timeout" | "error" | "skipped" | "disabled"
    duration_ms: int = 0
    candidate_count: int = 0


@dataclass
class RetrievedItem:
    kind: Kind
    id: str
    score: float
    layers: list[str]
    title: str
    content: str
    document_id: str | None = None
    section_path: str | None = None
    citation: str | None = None
    license_class: str = "unknown"
    source: str = ""
    is_table: bool = False


@dataclass
class RetrievalResult:
    items: list[RetrievedItem]
    traces: list[StageTrace]
    profile: str

    def trace_for(self, stage: str) -> StageTrace | None:
        return next((t for t in self.traces if t.stage == stage), None)

    @property
    def degraded_stages(self) -> list[str]:
        return [t.stage for t in self.traces if t.status in ("timeout", "error")]


@dataclass
class FusedCandidate:
    key: Key
    score: float
    layers: list[str] = field(default_factory=list)
