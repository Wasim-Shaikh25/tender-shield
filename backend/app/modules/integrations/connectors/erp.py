"""Generic ERP live connector stub (TS-333)."""

from __future__ import annotations

import os
from typing import Any

from app.modules.integrations.connectors.base import BaseConnector
from app.modules.integrations.models import IntegrationSource


def _env(name: str) -> str | None:
    return os.environ.get(name) or None


class ERPConnector(BaseConnector):
    name = "erp"
    auth_required = False

    def authorization_url(
        self, source: IntegrationSource, redirect_uri: str, state: str
    ) -> str | None:
        return None

    def exchange_code(
        self, source: IntegrationSource, code: str, redirect_uri: str
    ) -> dict[str, Any]:
        return {}

    def fetch(self, source: IntegrationSource) -> dict[str, Any]:
        return {
            "documents": [],
            "events": [],
            "cost_lines": [],
            "activities": [],
            "errors": [
                "ERP live fetch is not configured"
                " (TS_ERP_BASE_URL and API key missing)."
            ],
        }
