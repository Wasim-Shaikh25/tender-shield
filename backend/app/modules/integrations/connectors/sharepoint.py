"""SharePoint / OneDrive live connector stub (TS-333)."""

from __future__ import annotations

import os
from typing import Any

from app.modules.integrations.connectors.base import BaseConnector
from app.modules.integrations.models import IntegrationSource


def _env(name: str) -> str | None:
    return os.environ.get(name) or None


class SharePointConnector(BaseConnector):
    name = "sharepoint"

    def authorization_url(
        self, source: IntegrationSource, redirect_uri: str, state: str
    ) -> str | None:
        client_id = _env("TS_SHAREPOINT_CLIENT_ID")
        tenant = _env("TS_SHAREPOINT_TENANT") or "common"
        auth_url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
        if not client_id:
            return None
        return (
            f"{auth_url}?response_type=code&client_id={client_id}"
            f"&redirect_uri={redirect_uri}&state={state}"
            f"&scope=Files.Read.All Sites.Read.All offline_access"
        )

    def exchange_code(
        self, source: IntegrationSource, code: str, redirect_uri: str
    ) -> dict[str, Any]:
        return {
            "access_token": "",
            "refresh_token": "",
            "expires_at": None,
            "note": (
                "SharePoint OAuth requires TS_SHAREPOINT_CLIENT_SECRET"
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
                "SharePoint live fetch is not configured"
                " (Microsoft Graph token missing)."
            ],
        }
