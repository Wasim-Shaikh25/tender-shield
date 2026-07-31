"""Thin OpenRouter (OpenAI-compatible) client factory.

OpenRouter lets us route to many providers through one OpenAI-shaped endpoint.
The client is only instantiated when an API key is configured, so the app boots
and tests cleanly without the `openai` package or any key.

Every client returned here is wrapped by `MeteredClient` so that token usage is
recorded once, at the single choke point, rather than at each call site (TS-223).
A new call site therefore cannot forget to meter itself.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from app.core.config import Settings
from app.core.costmeter import record_llm_usage

logger = logging.getLogger(__name__)


class _MeteredCompletions:
    """Proxies `chat.completions`, recording usage from every response."""

    def __init__(self, inner: Any, stage: str) -> None:
        self._inner = inner
        self._stage = stage

    def create(self, *args: Any, **kwargs: Any) -> Any:
        response = self._inner.create(*args, **kwargs)
        try:
            usage = getattr(response, "usage", None)
            if usage is not None:
                cached = 0
                details = getattr(usage, "prompt_tokens_details", None)
                if details is not None:
                    cached = getattr(details, "cached_tokens", 0) or 0
                record_llm_usage(
                    model=str(kwargs.get("model") or getattr(response, "model", "unknown")),
                    stage=self._stage,
                    prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                    completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                    cached_tokens=cached,
                )
        except Exception:  # pragma: no cover - metering must never break a call
            logger.exception("failed to record LLM usage; response returned unchanged")
        return response

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class _MeteredChat:
    def __init__(self, inner: Any, stage: str) -> None:
        self._inner = inner
        self.completions = _MeteredCompletions(inner.completions, stage)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class MeteredClient:
    """OpenAI-shaped client that records token usage for every chat completion.

    Everything other than `chat.completions.create` passes straight through, so
    this stays a metering wrapper rather than an abstraction over the SDK.
    """

    def __init__(self, inner: Any, stage: str = "unknown") -> None:
        self._inner = inner
        self._stage = stage
        self.chat = _MeteredChat(inner.chat, stage)

    def with_stage(self, stage: str) -> MeteredClient:
        """Return a view of this client that attributes calls to `stage`."""
        return MeteredClient(self._inner, stage)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def openrouter_client(stage: str = "unknown") -> MeteredClient | None:
    """Return a metered OpenAI-compatible client for OpenRouter, or None if no key.

    `stage` labels the calls for per-stage cost attribution (e.g. "risk.classify",
    "assistant.chat", "analytics.plan").
    """
    settings = Settings()
    if settings.openrouter_api_key:
        key = settings.openrouter_api_key.get_secret_value()
    else:
        key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        return None

    headers: dict[str, str] = {}
    if settings.openrouter_site_url:
        headers["HTTP-Referer"] = settings.openrouter_site_url
    if settings.openrouter_app_name:
        headers["X-Title"] = settings.openrouter_app_name

    # Imported lazily so environments without the optional `openai` dependency
    # can still run the deterministic code paths.
    from openai import OpenAI

    return MeteredClient(
        OpenAI(
            base_url=settings.openrouter_base_url,
            api_key=key,
            default_headers=headers,
        ),
        stage=stage,
    )
