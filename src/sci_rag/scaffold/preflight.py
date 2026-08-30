"""Bounded model credential checks shared by setup and ``sci-rag doctor``."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from google.auth.exceptions import DefaultCredentialsError

from sci_rag.config import Settings

if TYPE_CHECKING:
    from sci_rag.llm import LLMClient

_CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


@dataclass(frozen=True)
class CredentialProbe:
    """A user-safe probe result that never carries the credential itself."""

    ok: bool
    detail: str
    fix: str = ""


def explicit_google_settings(
    *,
    api_key: str = "",
    gcp_project: str = "",
    location: str = "us-central1",
    model: str = "gemini-2.5-flash",
) -> Settings:
    """Build settings without reading a parent project's ``.env`` file."""
    return Settings.model_validate(
        {
            "google_api_key": api_key or None,
            "gcp_project": gcp_project or None,
            "gcp_location": location,
            "llm_provider": "google",
            "llm_model": model,
            "embedding_provider": "google",
        }
    )


def build_explicit_google_llm(
    *,
    api_key: str = "",
    gcp_project: str = "",
    location: str = "us-central1",
    model: str = "gemini-2.5-flash",
) -> LLMClient:
    """Build a client from captured values without consulting ambient settings."""
    from sci_rag.llm import get_llm

    settings = explicit_google_settings(
        api_key=api_key,
        gcp_project=gcp_project,
        location=location,
        model=model,
    )
    return get_llm(settings, api_key_override=api_key or None)


def probe_google_credentials(
    *,
    api_key: str = "",
    gcp_project: str = "",
    location: str = "us-central1",
    model: str = "gemini-2.5-flash",
    timeout_s: float = 15.0,
) -> CredentialProbe:
    """Make one bounded generation call with an explicit Google credential."""
    if not api_key and not gcp_project:
        return CredentialProbe(
            False,
            "No Google credential was provided.",
            "Add an AI Studio key or a Google Cloud project, then try again.",
        )
    settings = explicit_google_settings(
        api_key=api_key,
        gcp_project=gcp_project,
        location=location,
        model=model,
    )
    return asyncio.run(
        probe_model_credentials(
            settings,
            api_key_override=api_key or None,
            timeout_s=timeout_s,
        )
    )


async def probe_model_credentials(
    settings: Settings,
    *,
    api_key_override: str | None = None,
    timeout_s: float = 15.0,
) -> CredentialProbe:
    """Probe configured generation with a hard deadline and safe error copy."""
    try:
        return await asyncio.wait_for(
            _generate_once(settings, api_key_override=api_key_override),
            timeout=timeout_s,
        )
    except TimeoutError:
        return CredentialProbe(
            False,
            f"Credential check timed out after {timeout_s:g} seconds.",
            "Check the network or proxy, then try again.",
        )
    except Exception as exc:
        return _failure_result(
            exc,
            vertex=settings.credentials_mode() == "vertex",
            location=settings.gcp_location,
        )


async def _generate_once(settings: Settings, *, api_key_override: str | None) -> CredentialProbe:
    if settings.credentials_mode() == "vertex":
        import google.auth

        await asyncio.to_thread(google.auth.default, scopes=[_CLOUD_PLATFORM_SCOPE])

    from sci_rag.llm import get_llm

    llm = get_llm(settings, api_key_override=api_key_override)
    start = time.monotonic()
    # Reasoning models may spend output tokens before producing the visible
    # word. A generous cap avoids misclassifying that as an empty response;
    # the hard wall-clock timeout still bounds the probe.
    reply = await llm.generate("Reply with the single word: ready", max_tokens=2048)
    elapsed_ms = int((time.monotonic() - start) * 1000)
    if not reply.strip():
        return CredentialProbe(
            False,
            f"{llm.describe()} returned an empty response.",
            "Check the model name and quota, then try again.",
        )
    return CredentialProbe(True, f"{llm.describe()} answered in {elapsed_ms} ms.")


#: Vertex refuses a model served somewhere else in two stable shapes. The
#: first says the model exists and this region does not serve it. The second
#: is a plain 404, which covers the same cause plus two others: a model id
#: that is wrong, and a Model Garden offering the project never enabled.
_NOT_SERVABLE_MARKERS = ("not servable in region", "not servable in location")
_NOT_FOUND_MARKERS = ("not found in location", "not found in region")


def _failure_result(exc: Exception, *, vertex: bool, location: str = "") -> CredentialProbe:
    """Translate provider failures without copying exception text or secrets.

    The raw messages name an internal resource path, so every branch builds
    its own sentence from values the caller already holds rather than
    forwarding the provider's.
    """
    if isinstance(exc, DefaultCredentialsError):
        return CredentialProbe(
            False,
            "Application Default Credentials were not found.",
            "Run `gcloud auth application-default login`, then try again.",
        )

    message = str(exc).lower()
    if any(
        marker in message
        for marker in ("service_disabled", "api is disabled", "has not been used", "not enabled")
    ):
        return CredentialProbe(
            False,
            "The Google model API is not enabled for this project.",
            "Enable the Generative Language API or Vertex AI API for the project, then retry.",
        )
    if not vertex and any(
        marker in message
        for marker in ("api key not valid", "invalid api key", "api_key_invalid", "unauthenticated")
    ):
        return CredentialProbe(
            False,
            "Google rejected the API key.",
            "Create or copy a valid key from https://aistudio.google.com/apikey.",
        )
    if vertex and any(
        marker in message
        for marker in ("default credentials", "could not automatically determine credentials")
    ):
        return CredentialProbe(
            False,
            "Application Default Credentials were not found.",
            "Run `gcloud auth application-default login`, then try again.",
        )
    where = f" in {location}" if location else ""
    if any(marker in message for marker in _NOT_SERVABLE_MARKERS):
        return CredentialProbe(
            False,
            f"The model is not served{where}.",
            "Partner models such as Claude and Grok are served from the global "
            "location. Set SCI_RAG_GCP_LOCATION=global and try again.",
        )
    if any(marker in message for marker in _NOT_FOUND_MARKERS):
        return CredentialProbe(
            False,
            f"The model was not found{where}.",
            "Set SCI_RAG_GCP_LOCATION=global if this is a partner model such as "
            "Claude or Grok, which are served only from there. If it is already "
            "global, check the model id and that the model's Model Garden "
            "offering is enabled for this project.",
        )
    if isinstance(exc, (ConnectionError, OSError)) or any(
        marker in message
        for marker in ("connection", "network", "dns", "name resolution", "unreachable")
    ):
        return CredentialProbe(
            False,
            "Could not reach the Google model service.",
            "Check the network or proxy, then try again.",
        )

    fix = (
        "Check the project ID, ADC login, API enablement, model, and quota."
        if vertex
        else "Check the AI Studio key, model, and quota, then try again."
    )
    return CredentialProbe(False, f"Credential check failed ({type(exc).__name__}).", fix)
