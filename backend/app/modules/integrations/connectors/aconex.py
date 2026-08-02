"""Aconex (Oracle) live connector stub (TS-333)."""

from __future__ import annotations

import os
from typing import Any

from app.modules.integrations.connectors.base import BaseConnector
from app.modules.integrations.models import IntegrationSource


def _env(name: str) -> str | None:
    return os.environ.get(name) or None


class AconexConnector(BaseConnector):
    name = "aconex"

    def authorization_url(
        self, source: IntegrationSource, redirect_uri: str, state: str
    ) -> str | None:
        client_id = _env("TS_ACONEX_CLIENT_ID")
        auth_url = _env("TS_ACONEX_AUTH_URL") or "https://connect.aconex.com/api/oauth/authorize"
        if not client_id:
            return None
        return (
            f"{auth_url}?response_type=code&client_id={client_id}"
            f"&redirect_uri={redirect_uri}&state={state}"
        )

    def exchange_code(
        self, source: IntegrationSource, code: str, redirect_uri: str
    ) -> dict[str, Any]:
        return {
            "access_token": "",
            "refresh_token": "",
            "expires_at": None,
            "note": (
                "Aconex OAuth requires TS_ACONEX_CLIENT_SECRET"
                " and a live token call; not performed."
            ),
        }

    def fetch(self, source: IntegrationSource) -> dict[str, Any]:
        return {
            "documents": [],
            "events": [],
            "cost_lines": [],
            "activities": [],
            "errors": [
                "Aconex live fetch is not configured"
                " (TS_ACONEX_BASE_URL and token missing)."
            ],
        }
