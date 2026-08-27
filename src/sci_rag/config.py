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
from typing import TYPE_CHECKING, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from sci_rag.llm.spec import ModelSpec

CredentialsMode = Literal["api_key", "vertex", "none"]

#: Generation backends the kit ships an adapter for. Embeddings deliberately
#: stay Google-only; see docs/adr/0006-multi-provider-llms.md.
LLMProviderName = Literal["google", "anthropic", "openai-compatible"]

#: Where a generation call comes from. Each role resolves to its own model
#: spec so a cheap model can do high-volume extraction while a stronger one
#: writes answers, and a *different* one grades them.
LLMRole = Literal["answer", "extraction", "judge"]


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

    # --- Credentials for the non-Google generation providers ----------------
    # Anthropic on Vertex uses ``gcp_project`` and application-default
    # credentials; this key is only for the direct Anthropic API.
    anthropic_api_key: str | None = None
    # The OpenAI-compatible provider points at Vertex Model Garden by default
    # (Grok, Llama, Mistral, DeepSeek) using application-default credentials.
    # Set a base URL to target OpenAI itself or a self-hosted server instead.
    openai_api_key: str | None = None
    openai_base_url: str | None = None

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
    # The provider a bare model id belongs to. Any model setting below may
    # override it inline as "provider:model".
    llm_provider: LLMProviderName = "google"
    llm_model: str = "gemini-2.5-flash"
    # Cheap-and-fast model for high-volume extraction calls. Defaults to
    # ``llm_model`` when unset.
    extraction_model: str | None = None
    # Model for the evaluation judge. Pointing it at a different provider than
    # ``llm_model`` avoids grading a model's answers with its own family.
    judge_model: str | None = None

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

    @property
    def resolved_judge_model(self) -> str:
        return self.judge_model or self.llm_model

    def model_spec_for(self, role: LLMRole) -> ModelSpec:
        """The provider and model id a given call site should use."""
        # Imported here because sci_rag.llm imports this module; the lazy
        # import keeps the package graph acyclic.
        from sci_rag.llm.spec import parse_model_spec

        raw = {
            "answer": self.llm_model,
            "extraction": self.resolved_extraction_model,
            "judge": self.resolved_judge_model,
        }[role]
        return parse_model_spec(raw, default_provider=self.llm_provider)

    def credentials_mode(self) -> CredentialsMode:
        """Which Google credential path is configured, if any.

        An explicit API key wins over a Vertex project so that a laptop user
        with both can predict what happens. This covers embeddings and the
        Google generation provider; the other providers carry their own
        credentials.
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
