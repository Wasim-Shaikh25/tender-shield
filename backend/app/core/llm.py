"""Thin OpenRouter (OpenAI-compatible) client factory.

OpenRouter lets us route to many providers through one OpenAI-shaped endpoint.
The client is only instantiated when an API key is configured, so the app boots
and tests cleanly without the `openai` package or any key.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from app.core.config import Settings

if TYPE_CHECKING:
    from openai import OpenAI


def openrouter_client() -> OpenAI | None:
    """Return a configured OpenAI client pointing at OpenRouter, or None if no key."""
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

    return OpenAI(
        base_url=settings.openrouter_base_url,
        api_key=key,
        default_headers=headers,
    )
