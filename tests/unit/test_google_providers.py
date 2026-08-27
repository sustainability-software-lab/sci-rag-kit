"""Offline tests for the Google providers, via a stub genai client.

Network code cannot run in CI, but its logic can: batching, Matryoshka
re-normalization, dimension assertions, retry/backoff, and the Gemini 2.5
thinking fallback are all exercised against a scripted stand-in.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

import sci_rag.embed.google as embed_google
import sci_rag.llm.client as llm_client
import sci_rag.llm.google as llm_google
from sci_rag.config import Settings
from sci_rag.embed import EmbeddingDimensionError
from sci_rag.embed.google import GoogleEmbedder, make_genai_client


def _settings(**overrides):  # type: ignore[no-untyped-def]
    values = {
        "google_api_key": "test-key",
        "embedding_model": "gemini-embedding-001",
        "embedding_dim": 4,
        "llm_model": "gemini-2.5-flash",
    }
    values.update(overrides)
    return Settings(**values)


class StubEmbeddingClient:
    """Returns scripted vectors; records every call; can fail first."""

    def __init__(self, vectors_per_call, failures=0, failure_text="429 slow down"):  # type: ignore[no-untyped-def]
        self.vectors_per_call = list(vectors_per_call)
        self.failures = failures
        self.failure_text = failure_text
        self.calls: list[list[str]] = []
        self.aio = SimpleNamespace(models=SimpleNamespace(embed_content=self._embed))

    async def _embed(self, *, model, contents, config):  # type: ignore[no-untyped-def]
        self.calls.append(list(contents))
        if self.failures:
            self.failures -= 1
            raise RuntimeError(self.failure_text)
        vectors = self.vectors_per_call.pop(0)
        return SimpleNamespace(embeddings=[SimpleNamespace(values=vector) for vector in vectors])


@pytest.fixture(autouse=True)
def _fast_backoff(monkeypatch):  # type: ignore[no-untyped-def]
    async def no_sleep(_seconds):  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr(embed_google.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(llm_client.asyncio, "sleep", no_sleep)


async def test_embedder_batches_and_renormalizes() -> None:
    texts = [f"t{i}" for i in range(25)]  # crosses the 20-per-call batch line
    first = [[2.0, 0.0, 0.0, 0.0]] * 20
    second = [[0.0, 3.0, 0.0, 0.0]] * 5
    client = StubEmbeddingClient([first, second])
    embedder = GoogleEmbedder(_settings(), client=client)  # type: ignore[arg-type]

    vectors = await embedder.embed(texts, task="document")
    assert len(client.calls) == 2
    assert [len(call) for call in client.calls] == [20, 5]
    # Matryoshka-truncated vectors are not unit norm; the embedder must fix that.
    assert all(math.isclose(sum(v * v for v in vec), 1.0, rel_tol=1e-9) for vec in vectors)
    assert vectors[0][0] == 1.0 and vectors[24][1] == 1.0


async def test_embedder_rejects_wrong_dimension() -> None:
    client = StubEmbeddingClient([[[1.0, 0.0]]])  # 2 dims, settings say 4
    embedder = GoogleEmbedder(_settings(), client=client)  # type: ignore[arg-type]
    with pytest.raises(EmbeddingDimensionError, match="vector\\(4\\)"):
        await embedder.embed(["x"], task="query")


async def test_embedder_retries_transient_errors_then_succeeds() -> None:
    client = StubEmbeddingClient([[[0.0, 0.0, 1.0, 0.0]]], failures=2)
    embedder = GoogleEmbedder(_settings(), client=client)  # type: ignore[arg-type]
    [vector] = await embedder.embed(["x"], task="query")
    assert vector[2] == 1.0
    assert len(client.calls) == 3  # two failures plus the success


async def test_embedder_gives_up_on_non_retryable_errors() -> None:
    client = StubEmbeddingClient([], failures=5, failure_text="400 invalid argument")
    embedder = GoogleEmbedder(_settings(), client=client)  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="400"):
        await embedder.embed(["x"], task="query")
    assert len(client.calls) == 1  # no retry on a caller error


def test_make_genai_client_requires_credentials() -> None:
    with pytest.raises(RuntimeError, match="local-hash"):
        make_genai_client(Settings(google_api_key=None, gcp_project=None))


class StubGenerateClient:
    """Scripted generate_content: can reject the thinking knob or rate-limit."""

    def __init__(self, *, reject_thinking=False, failures=0, text="hello"):  # type: ignore[no-untyped-def]
        self.reject_thinking = reject_thinking
        self.failures = failures
        self.text = text
        self.configs: list[object] = []
        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=self._generate))

    async def _generate(self, *, model, contents, config):  # type: ignore[no-untyped-def]
        # Snapshot the knob's value: the fallback path mutates the same
        # config object, so storing the reference would alias the history.
        self.configs.append(config.thinking_config)
        if self.reject_thinking and config.thinking_config is not None:
            raise RuntimeError("thinking is not supported for this model")
        if self.failures:
            self.failures -= 1
            raise RuntimeError("503 UNAVAILABLE")
        return SimpleNamespace(text=self.text)


def _llm_with(monkeypatch, client):  # type: ignore[no-untyped-def]
    monkeypatch.setattr(embed_google, "make_genai_client", lambda *a, **k: client)
    return llm_google.GoogleLLM(_settings())


async def test_json_mode_disables_thinking(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    client = StubGenerateClient(text='{"ok": true}')
    llm = _llm_with(monkeypatch, client)
    payload = await llm.generate_json("give me json")
    assert payload == {"ok": True}
    assert client.configs[0] is not None
    assert client.configs[0].thinking_budget == 0

    await llm.generate("plain prose")
    assert client.configs[1] is None


async def test_thinking_knob_rejection_falls_back(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    client = StubGenerateClient(reject_thinking=True, text='{"ok": 1}')
    llm = _llm_with(monkeypatch, client)
    payload = await llm.generate_json("json please")
    assert payload == {"ok": 1}
    # First attempt carried the knob, the fallback dropped it.
    assert client.configs[0] is not None
    assert client.configs[-1] is None


async def test_generate_retries_unavailable(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    client = StubGenerateClient(failures=1, text="recovered")
    llm = _llm_with(monkeypatch, client)
    assert await llm.generate("q") == "recovered"
    assert len(client.configs) == 2
