"""Credential preflight is bounded, actionable, and safe to run offline in tests."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from google.auth.exceptions import DefaultCredentialsError

from sci_rag.config import Settings
from sci_rag.scaffold.preflight import (
    CredentialProbe,
    explicit_google_settings,
    probe_google_credentials,
)


class _Client:
    def __init__(self, *, reply: str = "ready", failure: Exception | None = None) -> None:
        self.reply = reply
        self.failure = failure
        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=self.generate_content))

    async def generate_content(self, **_kwargs):  # type: ignore[no-untyped-def]
        if self.failure is not None:
            raise self.failure
        return SimpleNamespace(text=self.reply)


def _install_client(monkeypatch, *, failure: Exception | None = None) -> list[dict[str, object]]:  # type: ignore[no-untyped-def]
    calls: list[dict[str, object]] = []

    def factory(**kwargs):  # type: ignore[no-untyped-def]
        calls.append(kwargs)
        return _Client(failure=failure)

    monkeypatch.setattr("google.genai.Client", factory)
    return calls


def test_ai_studio_key_can_complete_a_tiny_generation_probe(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls = _install_client(monkeypatch)

    result = probe_google_credentials(api_key="test-secret-key", timeout_s=1)

    assert result.ok is True
    assert "gemini-2.5-flash" in result.detail
    assert calls == [{"api_key": "test-secret-key"}]
    assert "test-secret-key" not in repr(result)


def test_explicit_settings_ignore_a_parent_project_dotenv(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / ".env").write_text(
        "SCI_RAG_GOOGLE_API_KEY=ambient-parent-key\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    settings = explicit_google_settings(gcp_project="selected-project")

    assert settings.google_api_key is None
    assert settings.gcp_project == "selected-project"


def test_vertex_checks_adc_before_calling_the_model(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls = _install_client(monkeypatch)
    adc_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "google.auth.default",
        lambda **kwargs: adc_calls.append(kwargs) or (SimpleNamespace(), "detected-project"),
    )

    result = probe_google_credentials(gcp_project="science-project", timeout_s=1)

    assert result.ok is True
    assert adc_calls
    assert calls == [{"vertexai": True, "project": "science-project", "location": "us-central1"}]


def test_missing_adc_names_the_login_command(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _install_client(monkeypatch)

    def missing(**_kwargs):  # type: ignore[no-untyped-def]
        raise DefaultCredentialsError("credentials not found")

    monkeypatch.setattr("google.auth.default", missing)

    result = probe_google_credentials(gcp_project="science-project", timeout_s=1)

    assert result == CredentialProbe(
        ok=False,
        detail="Application Default Credentials were not found.",
        fix="Run `gcloud auth application-default login`, then try again.",
    )


@pytest.mark.parametrize(
    ("failure", "detail", "fix_fragment"),
    [
        (
            RuntimeError("400 API key not valid. Please pass a valid API key."),
            "Google rejected the API key.",
            "aistudio.google.com/apikey",
        ),
        (
            RuntimeError("403 SERVICE_DISABLED: Generative Language API is disabled"),
            "The Google model API is not enabled for this project.",
            "Enable",
        ),
        (
            ConnectionError("DNS lookup failed"),
            "Could not reach the Google model service.",
            "network",
        ),
    ],
)
def test_common_failures_map_to_concrete_fixes(
    monkeypatch, failure: Exception, detail: str, fix_fragment: str
) -> None:  # type: ignore[no-untyped-def]
    _install_client(monkeypatch, failure=failure)

    result = probe_google_credentials(api_key="never-print-this", timeout_s=1)

    assert result.ok is False
    assert result.detail == detail
    assert fix_fragment in result.fix
    assert "never-print-this" not in repr(result)


def test_probe_timeout_is_reported_without_leaking_an_exception(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    class SlowClient(_Client):
        async def generate_content(self, **_kwargs):  # type: ignore[no-untyped-def]
            await asyncio.Event().wait()

    monkeypatch.setattr("google.genai.Client", lambda **_kwargs: SlowClient())

    result = probe_google_credentials(api_key="slow-key", timeout_s=0.01)

    assert result.ok is False
    assert "timed out" in result.detail
    assert "network" in result.fix


async def test_doctor_generation_probe_uses_the_shared_failure_mapping(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from sci_rag.cli.doctor import _live_probe

    async def failed(_settings, **_kwargs):  # type: ignore[no-untyped-def]
        return CredentialProbe(False, "Mapped provider failure.", "Use the mapped fix.")

    monkeypatch.setattr("sci_rag.scaffold.preflight.probe_model_credentials", failed)

    checks = await _live_probe(Settings(_env_file=None, embedding_provider="local-hash"))
    generation = next(check for check in checks if check.name == "generation probe")

    assert generation.status == "fail"
    assert generation.detail == "Mapped provider failure."
    assert generation.fix == "Use the mapped fix."
