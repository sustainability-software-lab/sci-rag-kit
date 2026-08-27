"""The LLM interface used everywhere generation happens.

One abstraction covers answer generation, graph extraction, HyDE passages,
community summaries, and the evaluation judge. The default implementation
talks to Gemini through google-genai in either credential mode (AI Studio
API key or Vertex AI). Tests use :class:`MockLLM`, which replays canned
responses and records every prompt it saw.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import structlog

from sci_rag.config import Settings

log = structlog.get_logger(__name__)

# The google-genai SDK logs an advisory about automatic function calling on
# every generate_content call; we do not use AFC, so keep the noise down.
logging.getLogger("google_genai.models").setLevel(logging.ERROR)

_MAX_ATTEMPTS = 3


def _is_retryable(exc: Exception) -> bool:
    text = str(exc)
    return any(
        marker in text for marker in ("429", "503", "500", "RESOURCE_EXHAUSTED", "UNAVAILABLE")
    )


class LLMClient(ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        json_mode: bool = False,
    ) -> str:
        """Return the model's full text response."""

    @abstractmethod
    def stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        """Yield the response incrementally as text deltas."""

    async def generate_json(
        self, prompt: str, *, system: str | None = None, max_tokens: int = 4096
    ) -> Any:
        """Generate and parse a JSON response, tolerating code fences."""
        raw = await self.generate(
            prompt, system=system, temperature=0.0, max_tokens=max_tokens, json_mode=True
        )
        return parse_json_loosely(raw)


def parse_json_loosely(raw: str) -> Any:
    """Parse model output as JSON, stripping markdown fences if present."""
    text = raw.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL)
    if fence:
        text = fence.group(1)
    return json.loads(text)


class GoogleLLM(LLMClient):
    def __init__(
        self,
        settings: Settings,
        *,
        model: str | None = None,
        api_key_override: str | None = None,
    ) -> None:
        # Imported here so offline paths never load the SDK.
        from sci_rag.embed.google import make_genai_client

        self._client = make_genai_client(settings, api_key_override=api_key_override)
        self.model = model or settings.llm_model

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        json_mode: bool = False,
    ) -> str:
        from google.genai import types

        # Gemini 2.5 models "think" by default, and thought tokens count
        # against max_output_tokens. On high-volume structured calls
        # (extraction, judging) that turns into minutes of latency and
        # sometimes an empty response once the budget is spent on thought.
        # JSON-mode calls therefore disable thinking; if a model rejects the
        # knob we retry once without it.
        thinking_config = (
            types.ThinkingConfig(thinking_budget=0) if json_mode else None
        )
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_tokens,
            response_mime_type="application/json" if json_mode else None,
            thinking_config=thinking_config,
        )
        delay = 1.0
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                try:
                    response = await self._client.aio.models.generate_content(
                        model=self.model, contents=prompt, config=config
                    )
                except Exception as exc:
                    # Some models reject the thinking knob outright; drop it
                    # and try again rather than failing the whole call.
                    if thinking_config is not None and "thinking" in str(exc).lower():
                        config.thinking_config = None
                        thinking_config = None
                        response = await self._client.aio.models.generate_content(
                            model=self.model, contents=prompt, config=config
                        )
                    else:
                        raise
                return response.text or ""
            except Exception as exc:
                if attempt == _MAX_ATTEMPTS or not _is_retryable(exc):
                    raise
                log.warning("llm_retry", attempt=attempt, delay_s=delay, error=type(exc).__name__)
                await asyncio.sleep(delay)
                delay *= 2
        raise AssertionError("unreachable")

    async def _stream_impl(
        self, prompt: str, system: str | None, temperature: float, max_tokens: int
    ) -> AsyncIterator[str]:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        stream = await self._client.aio.models.generate_content_stream(
            model=self.model, contents=prompt, config=config
        )
        async for chunk in stream:
            if chunk.text:
                yield chunk.text

    def stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        return self._stream_impl(prompt, system, temperature, max_tokens)


@dataclass
class MockLLM(LLMClient):
    """Deterministic stand-in for tests: replays queued responses in order.

    When the queue runs dry it returns ``default_response``, so tests only
    queue what they assert on.
    """

    responses: list[str] = field(default_factory=list)
    default_response: str = "{}"
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        json_mode: bool = False,
    ) -> str:
        self.calls.append(
            {"prompt": prompt, "system": system, "temperature": temperature, "json_mode": json_mode}
        )
        if self.responses:
            return self.responses.pop(0)
        return self.default_response

    async def _stream_impl(self, text: str) -> AsyncIterator[str]:
        # Stream in small pieces so consumers exercise their delta handling.
        for start in range(0, len(text), 24):
            yield text[start : start + 24]

    def stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        self.calls.append({"prompt": prompt, "system": system, "stream": True})
        text = self.responses.pop(0) if self.responses else self.default_response
        return self._stream_impl(text)


def get_llm(
    settings: Settings, *, model: str | None = None, api_key_override: str | None = None
) -> LLMClient:
    return GoogleLLM(settings, model=model, api_key_override=api_key_override)
