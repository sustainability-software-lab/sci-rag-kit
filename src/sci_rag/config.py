"""Runtime configuration for sci-rag-kit.

Everything is driven by environment variables with the ``SCI_RAG_`` prefix
(or a local ``.env`` file; see ``.env.example`` for a guided tour). Domain
semantics (ontology, prompts, retrieval weights) live in ``domain/domain.yaml``
instead, so that specializing the kit to a new field never means editing
Python.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

CredentialsMode = Literal["api_key", "vertex", "none"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SCI_RAG_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Database -----------------------------------------------------------
    database_url: str = "postgresql+asyncpg://sci_rag:sci_rag@localhost:5433/sci_rag"

    # --- Google credentials (either an AI Studio key or a GCP project) ------
    google_api_key: str | None = None
    gcp_project: str | None = None
    gcp_location: str = "us-central1"

    # --- Embeddings ---------------------------------------------------------
    # "google" uses gemini-embedding-001 through whichever credential mode is
    # configured. "local-hash" is a deterministic, offline embedder for tests
    # and pipeline dry runs; its rankings are lexical, not semantic.
    embedding_provider: Literal["google", "local-hash"] = "google"
    embedding_model: str = "gemini-embedding-001"
    # 1536 stays inside pgvector's 2000-dimension HNSW index limit. The
    # database column is created with this dimension, so changing it after
    # ingestion requires a migration plus a re-embedding pass.
    embedding_dim: int = 1536

    # --- Generation (answers, graph extraction, HyDE, summaries) ------------
    llm_model: str = "gemini-2.5-flash"
    # Cheap-and-fast model for high-volume extraction calls. Defaults to
    # ``llm_model`` when unset.
    extraction_model: str | None = None

    # --- Retrieval stage timeouts (seconds) ---------------------------------
    # "interactive" keeps a user waiting; "deep" is for offline/agent use.
    interactive_stage_timeout_s: float = 8.0
    deep_stage_timeout_s: float = 30.0

    # --- Paths --------------------------------------------------------------
    domain_dir: Path = Path("domain")
    data_dir: Path = Path("data")

    # --- Server -------------------------------------------------------------
    server_host: str = "127.0.0.1"
    server_port: int = 8000
    # JSON map of API key -> {"scopes": [...], ...}. Unset means the server
    # runs open (fine on localhost; it warns loudly at startup).
    api_keys: str | None = None
    cors_origins: str = "*"

    @property
    def resolved_extraction_model(self) -> str:
        return self.extraction_model or self.llm_model

    def credentials_mode(self) -> CredentialsMode:
        """Which Google credential path is configured, if any.

        An explicit API key wins over a Vertex project so that a laptop user
        with both can predict what happens.
        """
        if self.google_api_key:
            return "api_key"
        if self.gcp_project:
            return "vertex"
        return "none"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    """Test hook: force settings to be re-read from the environment."""
    get_settings.cache_clear()
