"""Gemini generation via the google-genai SDK.

Works in either credential mode without code changes -- an AI Studio API key
or Vertex AI application-default credentials -- by reusing the same client
factory the Google embedder uses.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from sci_rag.config import Settings
from sci_rag.llm.client import LLMClient, retry_async

# The google-genai SDK logs an advisory about automatic function calling on
# every generate_content call; we do not use AFC, so keep the noise down.
logging.getLogger("google_genai.models").setLevel(logging.ERROR)


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

        self._client = make_genai_client(
            settings, api_key_override=api_key_override, purpose="generation"
        )
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
        thinking_config = types.ThinkingConfig(thinking_budget=0) if json_mode else None
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_tokens,
            response_mime_type="application/json" if json_mode else None,
            thinking_config=thinking_config,
        )
        state = {"thinking": thinking_config is not None}

        async def call() -> str:
            try:
                response = await self._client.aio.models.generate_content(
                    model=self.model, contents=prompt, config=config
                )
            except Exception as exc:
                # Some models reject the thinking knob outright; drop it and
                # try again rather than failing the whole call.
                if state["thinking"] and "thinking" in str(exc).lower():
                    config.thinking_config = None
                    state["thinking"] = False
                    response = await self._client.aio.models.generate_content(
                        model=self.model, contents=prompt, config=config
                    )
                else:
                    raise
            return response.text or ""

        return await retry_async(call)

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
