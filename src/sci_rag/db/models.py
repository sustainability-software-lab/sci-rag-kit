"""Database schema: documents, chunks, and the knowledge graph.

The whole knowledge base lives in one Postgres database. Text chunks carry
both a dense embedding (pgvector) and a generated full-text search vector,
and the knowledge graph is plain rows: entities, typed relationships between
them, and precomputed communities with summaries. No separate graph or
vector database to operate.

The embedding columns are created with a fixed dimension
(``SCI_RAG_EMBEDDING_DIM``, default 1536) by the initial migration. Changing
the dimension later means a migration plus a re-embedding pass; the embedder
asserts the dimension on every call so a mismatch fails loudly, not subtly.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from sci_rag.config import get_settings

EMBEDDING_DIM: int = get_settings().embedding_dim


def new_id() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    pass


class Document(Base):
    """One ingested source: a paper, a report, a protocol, a web page."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(Text)
    # Where this came from, in your own vocabulary ("local", "gcs", "county_ag_reports", ...).
    source: Mapped[str] = mapped_column(Text, default="local")
    # A stable pointer back to the original (path, URL, GCS URI).
    source_ref: Mapped[str | None] = mapped_column(Text)

    # Citation metadata; whatever you know is enough.
    authors: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    publication_year: Mapped[int | None] = mapped_column(Integer)
    doi: Mapped[str | None] = mapped_column(Text)
    formatted_citation: Mapped[str | None] = mapped_column(Text)

    # Redistribution rights, fail-closed: anything we cannot show is "unknown"
    # and gets excluded whenever a caller restricts the license scope.
    license_class: Mapped[str] = mapped_column(Text, default="unknown")
    license_source: Mapped[str | None] = mapped_column(Text)

    # SHA-256 of the normalized text; ingesting the same content twice is a no-op.
    content_hash: Mapped[str] = mapped_column(String(64))

    page_count: Mapped[int | None] = mapped_column(Integer)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    chunks: Mapped[list[Chunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        UniqueConstraint("content_hash", name="uq_documents_content_hash"),
        Index("ix_documents_source", "source"),
        Index("ix_documents_license_class", "license_class"),
    )


class Chunk(Base):
    """A retrieval unit: a few paragraphs, or one intact table."""

    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer)
    # Breadcrumb of the section hierarchy this chunk sits in ("2 Methods > 2.1 Feedstocks").
    section_path: Mapped[str | None] = mapped_column(Text)
    # Tables are chunked whole so rows never straddle two chunks.
    is_table: Mapped[bool] = mapped_column(Boolean, default=False)

    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    # Which model produced the vector, so a model upgrade can find stale rows.
    embedding_version: Mapped[str | None] = mapped_column(Text)

    # When the graph extractor last processed this chunk; NULL means "not
    # yet", which is how incremental extraction finds its work.
    graph_extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Kept in sync by Postgres itself; powers the keyword retrieval layer.
    search_tsv: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', content)", persisted=True),
    )

    document: Mapped[Document] = relationship(back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunks_doc_index"),
        Index("ix_chunks_document_id", "document_id"),
        Index("ix_chunks_embedding_version", "embedding_version"),
        # Approximate nearest-neighbor index for the dense retrieval layer.
        # This is why the default embedding dimension stays under pgvector's
        # 2000-dimension HNSW limit.
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        # Full-text index for the keyword retrieval layer.
        Index("ix_chunks_search_tsv", "search_tsv", postgresql_using="gin"),
    )


class KgEntity(Base):
    """A canonical concept extracted from the corpus (types come from domain.yaml)."""

    __tablename__ = "kg_entities"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(Text)
    entity_type: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    # Evidence pointers, denormalized for fast graph-to-chunk resolution.
    document_ids: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)
    chunk_ids: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("name", name="uq_kg_entities_name"),
        Index("ix_kg_entities_entity_type", "entity_type"),
    )


class KgRelationship(Base):
    """A directed, typed edge between two entities, with its evidence."""

    __tablename__ = "kg_relationships"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    source_entity_id: Mapped[str] = mapped_column(ForeignKey("kg_entities.id", ondelete="CASCADE"))
    target_entity_id: Mapped[str] = mapped_column(ForeignKey("kg_entities.id", ondelete="CASCADE"))
    relation_type: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    document_id: Mapped[str | None] = mapped_column(String(32))
    chunk_id: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_kg_relationships_source", "source_entity_id"),
        Index("ix_kg_relationships_target", "target_entity_id"),
        Index("ix_kg_relationships_type", "relation_type"),
    )


class KgCommunity(Base):
    """A cluster of related entities with an LLM-written summary.

    Community summaries answer the "big picture" questions that no single
    chunk covers. Because a stored summary aggregates evidence from many
    documents before any caller's scope is known, the community retrieval
    layer disables itself whenever license/source/exclusion filters are in
    play.
    """

    __tablename__ = "kg_communities"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(Text)
    level: Mapped[int] = mapped_column(Integer, default=0)
    member_entity_ids: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)
    summary: Mapped[str | None] = mapped_column(Text)
    summary_embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_kg_communities_level", "level"),)
