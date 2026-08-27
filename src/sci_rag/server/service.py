"""One service facade behind both front doors.

The REST routers and the MCP tools call the same :class:`RagService`
instance, so the two surfaces can never drift apart: same retrieval, same
scoping, same citations, same stats.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import ColumnElement, func, select

import sci_rag
from sci_rag.answer import AnswerEngine, AnswerEvent
from sci_rag.config import Settings, get_settings
from sci_rag.db.engine import get_session_factory
from sci_rag.db.models import Chunk, Document, KgCommunity, KgEntity, KgRelationship
from sci_rag.retrieve import RetrievalResult, RetrievalScope, Retriever
from sci_rag.server.errors import ApiError


class RagService:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        retriever: Retriever | None = None,
        answer_engine: AnswerEngine | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.retriever = retriever or Retriever(settings=self.settings)
        self.engine = answer_engine or AnswerEngine(
            settings=self.settings, retriever=self.retriever
        )
        self.session_factory = self.retriever.session_factory or get_session_factory()
        self.domain = self.retriever.domain

    @staticmethod
    def scope_from(
        license_classes: list[str] | None, sources: list[str] | None
    ) -> RetrievalScope | None:
        if license_classes is None and sources is None:
            return None
        return RetrievalScope(
            license_classes=tuple(license_classes) if license_classes is not None else None,
            sources=tuple(sources) if sources is not None else None,
        )

    async def retrieve(
        self,
        query: str,
        *,
        profile: str = "interactive",
        top_k: int = 8,
        license_classes: list[str] | None = None,
        sources: list[str] | None = None,
        include_graph: bool | None = None,
        include_community: bool | None = None,
        include_hyde: bool | None = None,
        include_rerank: bool | None = None,
    ) -> RetrievalResult:
        return await self.retriever.retrieve(
            query,
            profile=profile,
            limit=top_k,
            scope=self.scope_from(license_classes, sources),
            include_graph=include_graph,
            include_community=include_community,
            include_hyde=include_hyde,
            include_rerank=include_rerank,
        )

    def answer_stream(
        self,
        query: str,
        *,
        profile: str = "deep",
        top_k: int = 8,
        max_tokens: int = 2048,
        license_classes: list[str] | None = None,
        sources: list[str] | None = None,
        api_key_override: str | None = None,
    ) -> AsyncIterator[AnswerEvent]:
        return self.engine.answer_stream(
            query,
            profile=profile,
            limit=top_k,
            max_tokens=max_tokens,
            scope=self.scope_from(license_classes, sources),
            api_key_override=api_key_override,
        )

    async def list_documents(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        source: str | None = None,
        license_class: str | None = None,
    ) -> tuple[list[Document], int]:
        conditions: list[ColumnElement[bool]] = []
        if search:
            conditions.append(Document.title.ilike(f"%{search}%"))
        if source:
            conditions.append(Document.source == source)
        if license_class:
            conditions.append(Document.license_class == license_class)
        async with self.session_factory() as session:
            total = await session.scalar(select(func.count(Document.id)).where(*conditions))
            rows = (
                (
                    await session.execute(
                        select(Document)
                        .where(*conditions)
                        .order_by(Document.ingested_at.desc(), Document.id)
                        .offset((page - 1) * page_size)
                        .limit(page_size)
                    )
                )
                .scalars()
                .all()
            )
        return list(rows), int(total or 0)

    async def get_document(
        self, document_id: str, *, preview_chunks: int = 8, preview_chars: int = 240
    ) -> tuple[Document, list[Chunk]]:
        async with self.session_factory() as session:
            document = await session.get(Document, document_id)
            if document is None:
                raise ApiError(404, "document_not_found", "No such document", document_id)
            chunks = (
                (
                    await session.execute(
                        select(Chunk)
                        .where(Chunk.document_id == document_id)
                        .order_by(Chunk.chunk_index)
                        .limit(preview_chunks)
                    )
                )
                .scalars()
                .all()
            )
        return document, list(chunks)

    async def stats(self) -> dict[str, Any]:
        async with self.session_factory() as session:
            counts: dict[str, Any] = {}
            for label, model in (
                ("documents", Document),
                ("chunks", Chunk),
                ("entities", KgEntity),
                ("relationships", KgRelationship),
                ("communities", KgCommunity),
            ):
                counts[label] = int(await session.scalar(select(func.count(model.id))) or 0)
            counts["license_classes"] = {
                license_class: count
                for license_class, count in await session.execute(
                    select(Document.license_class, func.count(Document.id)).group_by(
                        Document.license_class
                    )
                )
            }
            counts["sources"] = {
                source: count
                for source, count in await session.execute(
                    select(Document.source, func.count(Document.id)).group_by(Document.source)
                )
            }
            counts["embedding_versions"] = {
                version or "none": count
                for version, count in (
                    await session.execute(
                        select(Chunk.embedding_version, func.count(Chunk.id)).group_by(
                            Chunk.embedding_version
                        )
                    )
                ).all()
            }
        return counts

    async def corpus_manifest(self, *, base_url: str = "") -> dict[str, Any]:
        stats = await self.stats()
        tuning = self.domain.config.retrieval
        return {
            "name": self.domain.name,
            "description": self.domain.config.description,
            "domain": self.domain.name,
            "kit": "sci-rag-kit",
            "kit_version": sci_rag.__version__,
            "stats": {
                "documents": stats["documents"],
                "chunks": stats["chunks"],
                "entities": stats["entities"],
                "communities": stats["communities"],
            },
            "embedding": {
                "model": self.settings.embedding_model,
                "provider": self.settings.embedding_provider,
                "dimension": self.settings.embedding_dim,
            },
            "retrieval": {
                "layers": ["vector", "keyword", "graph", "community", "hyde"],
                "fusion": "weighted_rrf",
                "rrf_k": tuning.rrf_k,
                "weights": tuning.weights,
            },
            "endpoints": {
                "rest": f"{base_url}/v1",
                "mcp": f"{base_url}/mcp",
                "openapi": f"{base_url}/openapi.json",
            },
            "features": {
                "byo_llm_key": True,
                "streaming": True,
                "license_scoping": True,
            },
        }

    async def database_healthy(self) -> bool:
        try:
            async with self.session_factory() as session:
                await session.execute(select(1))
            return True
        except Exception:
            return False
