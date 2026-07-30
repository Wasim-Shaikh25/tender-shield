"""TenderShield API client used by the Office MCP server.

Configure with:

    TENDERSHIELD_API_BASE=https://api.tendershield.example.com/api
    TENDERSHIELD_API_TOKEN=...        # JWT access token from /api/auth/login

If the variables are missing, TenderShield-aware tools return a setup message
instead of crashing.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

DEFAULT_TIMEOUT = 30.0


class TenderShieldClient:
    """Thin client for the TenderShield REST API."""

    def __init__(self, base_url: str | None = None, token: str | None = None) -> None:
        self.base_url = (base_url or os.environ.get("TENDERSHIELD_API_BASE", "")).rstrip("/")
        self.token = token or os.environ.get("TENDERSHIELD_API_TOKEN", "")
        self._client: httpx.Client | None = None

    def configured(self) -> bool:
        return bool(self.base_url and self.token)

    def _client_open(self) -> httpx.Client:
        if self._client is None:
            headers = {"authorization": f"Bearer {self.token}"} if self.token else {}
            self._client = httpx.Client(base_url=self.base_url, headers=headers, timeout=DEFAULT_TIMEOUT)
        return self._client

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        if not self.configured():
            raise RuntimeError(
                "TenderShield API not configured. Set TENDERSHIELD_API_BASE and TENDERSHIELD_API_TOKEN."
            )
        client = self._client_open()
        resp = client.request(method, path, **kwargs)
        resp.raise_for_status()
        if resp.content:
            return resp.json()
        return {}

    def _extract_items(self, data: Any, *keys: str) -> list[dict[str, Any]]:
        if isinstance(data, list):
            return list(data)
        if isinstance(data, dict):
            for key in keys:
                nested = data.get(key)
                if isinstance(nested, dict):
                    nested = nested.get("items")
                if isinstance(nested, list):
                    return list(nested)
        return []

    def list_opportunities(self) -> list[dict[str, Any]]:
        data = self._request("GET", "/ingestion/opportunities")
        return self._extract_items(data, "opportunities", "items")

    def get_opportunity(self, opportunity_id: str) -> dict[str, Any]:
        return self._request("GET", f"/ingestion/opportunities/{opportunity_id}")

    def get_deadlines(self, opportunity_id: str) -> list[dict[str, Any]]:
        data = self._request("GET", f"/ingestion/opportunities/{opportunity_id}/deadlines")
        return self._extract_items(data, "deadlines", "items")

    def get_findings(self, opportunity_id: str) -> list[dict[str, Any]]:
        data = self._request("GET", f"/findings/opportunities/{opportunity_id}")
        return self._extract_items(data, "findings", "items")

    def get_risk_summary(self, workspace_id: str | None = None) -> dict[str, Any]:
        params = {"workspace_id": workspace_id} if workspace_id else None
        return self._request("GET", "/analytics/risk-summary", params=params)

    def get_plan_dashboard(self, opportunity_id: str, query: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/analytics/plan",
            json={"opportunity_id": opportunity_id, "query": query},
        )

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self) -> "TenderShieldClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _format_json(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)
