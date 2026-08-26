"""Authentication: static API keys by default, a clean seam for OAuth later.

The default backend reads ``SCI_RAG_API_KEYS``, a JSON map of key to
settings::

    {"team-key-1": {"scopes": ["retrieval:query", "retrieval:answer"],
                    "rate_limit_per_minute": 60},
     "agent-key":  {"scopes": ["retrieval:query", "retrieval:answer",
                                "corpus:read", "byo_llm"]}}

With no keys configured the server runs OPEN (every request gets every
scope) and warns loudly at startup; that is the right default for
localhost development and the wrong one for anything public.

The seam for a real identity provider is the :class:`AuthBackend`
interface plus one line in the app factory; swap in an OAuth token
verifier without touching any route. Scopes are the contract:

* ``retrieval:query``: run retrieval
* ``retrieval:answer``: generate answers (spends LLM tokens)
* ``corpus:read``: browse the document catalog
* ``byo_llm``: allowed to supply a per-request LLM key
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field

import structlog
from fastapi import Depends, Request
from fastapi.security.utils import get_authorization_scheme_param

from sci_rag.server.errors import ApiError

log = structlog.get_logger(__name__)

ALL_SCOPES = ("retrieval:query", "retrieval:answer", "corpus:read", "byo_llm")


@dataclass
class AuthContext:
    key_id: str
    scopes: tuple[str, ...]
    llm_api_key: str | None = None  # per-key BYO binding; never logged
    rate_limit_per_minute: int | None = None

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes


class AuthBackend(ABC):
    @abstractmethod
    def authenticate(self, token: str | None) -> AuthContext:
        """Return the context for a bearer token, or raise :class:`ApiError`."""

    @abstractmethod
    def check_rate(self, context: AuthContext) -> None:
        """Raise :class:`ApiError` (429) when the key is over its limit."""


class OpenBackend(AuthBackend):
    """No keys configured: everything allowed. Development only."""

    def authenticate(self, token: str | None) -> AuthContext:
        return AuthContext(key_id="anonymous", scopes=ALL_SCOPES)

    def check_rate(self, context: AuthContext) -> None:
        return


class _MinuteWindowLimiter:
    """A small fixed-window limiter, per key, in process memory. Good enough
    for a single instance; put a shared limiter in front for fleets."""

    def __init__(self) -> None:
        self._windows: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))

    def allow(self, key_id: str, per_minute: int) -> tuple[bool, int]:
        window = int(time.time() // 60)
        current_window, used = self._windows[key_id]
        if current_window != window:
            current_window, used = window, 0
        if used >= per_minute:
            retry_after = 60 - int(time.time() % 60)
            return False, max(retry_after, 1)
        self._windows[key_id] = (current_window, used + 1)
        return True, 0


@dataclass
class StaticKeyBackend(AuthBackend):
    keys: dict[str, dict]
    default_rate_limit_per_minute: int = 120
    _limiter: _MinuteWindowLimiter = field(default_factory=_MinuteWindowLimiter)

    @classmethod
    def from_json(cls, raw: str) -> StaticKeyBackend:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"SCI_RAG_API_KEYS is not valid JSON: {exc}") from exc
        if not isinstance(parsed, dict) or not parsed:
            raise RuntimeError(
                "SCI_RAG_API_KEYS must be a non-empty JSON object of key -> settings."
            )
        return cls(keys=parsed)

    def authenticate(self, token: str | None) -> AuthContext:
        if not token:
            raise ApiError(
                401,
                "missing_key",
                "Authentication required",
                "Send an API key: Authorization: Bearer <key>.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        entry = self.keys.get(token)
        if entry is None:
            raise ApiError(
                401,
                "invalid_key",
                "Unknown API key",
                headers={"WWW-Authenticate": "Bearer"},
            )
        scopes = tuple(entry.get("scopes") or ALL_SCOPES)
        return AuthContext(
            key_id=f"key:{token[:6]}...",
            scopes=scopes,
            llm_api_key=entry.get("llm_api_key"),
            rate_limit_per_minute=entry.get(
                "rate_limit_per_minute", self.default_rate_limit_per_minute
            ),
        )

    def check_rate(self, context: AuthContext) -> None:
        if not context.rate_limit_per_minute:
            return
        allowed, retry_after = self._limiter.allow(context.key_id, context.rate_limit_per_minute)
        if not allowed:
            raise ApiError(
                429,
                "rate_limited",
                "Rate limit exceeded",
                f"This key allows {context.rate_limit_per_minute} requests per minute.",
                headers={"Retry-After": str(retry_after)},
            )


def build_auth_backend(api_keys_json: str | None) -> AuthBackend:
    if api_keys_json:
        return StaticKeyBackend.from_json(api_keys_json)
    log.warning(
        "auth_disabled",
        note="No SCI_RAG_API_KEYS configured; the server is open. Fine on localhost, not in public.",
    )
    return OpenBackend()


def require_scopes(*scopes: str):  # type: ignore[no-untyped-def]
    """FastAPI dependency: authenticate the bearer token and check scopes."""

    async def dependency(request: Request) -> AuthContext:
        backend: AuthBackend = request.app.state.auth_backend
        scheme, token = get_authorization_scheme_param(request.headers.get("Authorization", ""))
        context = backend.authenticate(token if scheme.lower() == "bearer" else None)
        for scope in scopes:
            if not context.has_scope(scope):
                raise ApiError(
                    403,
                    "insufficient_scope",
                    "Insufficient scope",
                    f"This operation requires the {scope!r} scope.",
                )
        backend.check_rate(context)
        return context

    return Depends(dependency)
