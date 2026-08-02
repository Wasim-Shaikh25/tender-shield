"""Generic dynamic REST connector (TS-334).

Reads connector configuration from the DB at runtime so non-technical users can
point TenderShield at any JSON REST API (ERP sandbox, Oracle, custom systems).
No generated code is stored or executed.
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import object_session

from app.modules.integrations.connectors.base import BaseConnector
from app.modules.integrations.models import DynamicConnectorConfig, IntegrationSource


def _resolve(obj: Any, path: str) -> Any:
    if path == "":
        return obj
    value = obj
    for part in path.split("."):
        if value is None:
            return None
        if part == "*":
            return value if isinstance(value, list) else [value]
        if part.isdigit() and isinstance(value, list):
            index = int(part)
            value = value[index] if 0 <= index < len(value) else None
        elif isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


def _collect(obj: Any, path: str) -> list[Any]:
    value = _resolve(obj, path)
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


class DynamicRestConnector(BaseConnector):
    name = "dynamic"
    auth_required = True

    def authorization_url(
        self, source: IntegrationSource, redirect_uri: str, state: str
    ) -> str | None:
        return None

    def exchange_code(
        self, source: IntegrationSource, code: str, redirect_uri: str
    ) -> dict[str, Any]:
        return {}

    def _config_for(self, source: IntegrationSource) -> DynamicConnectorConfig | None:
        session = object_session(source)
        if session is None:
            return None
        config_id = (source.config or {}).get("dynamic_connector_id")
        if not config_id:
            return None
        return session.scalar(
            select(DynamicConnectorConfig).where(
                DynamicConnectorConfig.id == uuid.UUID(str(config_id)),
                DynamicConnectorConfig.enabled == True,  # noqa: E712
            )
        )

    def _client(self, config: DynamicConnectorConfig) -> httpx.Client:
        headers = dict(config.headers or {})
        auth = None
        auth_config = config.auth_config or {}
        if config.auth_type == "bearer":
            token = auth_config.get("token", "")
            headers["Authorization"] = f"Bearer {token}"
        elif config.auth_type == "basic":
            auth = httpx.BasicAuth(
                auth_config.get("username", ""), auth_config.get("password", "")
            )
        elif config.auth_type == "api_key":
            header_name = auth_config.get("header_name", "X-Api-Key")
            headers[header_name] = auth_config.get("api_key", "")
        return httpx.Client(base_url=config.base_url, headers=headers, auth=auth, timeout=30.0)

    def _page_params(self, config: DynamicConnectorConfig, page: int) -> dict[str, Any]:
        params: dict[str, Any] = {}
        pagination = config.pagination or {}
        ptype = pagination.get("type", "none")
        if ptype == "offset":
            limit = pagination.get("limit", 100)
            offset = page * limit
            params[pagination.get("offset_param", "offset")] = offset
            params[pagination.get("limit_param", "limit")] = limit
        elif ptype == "cursor" and page > 0:
            # cursor is injected by caller
            pass
        return params

    def _collect_mapped(
        self, config: DynamicConnectorConfig, kind: str, data: Any
    ) -> list[dict[str, Any]]:
        mapping = (config.mappings or {}).get(kind) or {}
        items_path = mapping.get("items", "")
        fields = mapping.get("fields") or {}
        if not fields:
            return []
        rows: list[dict[str, Any]] = []
        for item in _collect(data, items_path):
            row: dict[str, Any] = {}
            for target, source_path in fields.items():
                value = _resolve(item, source_path)
                if value is not None:
                    row[target] = value
            if row:
                rows.append(row)
        return rows

    def fetch(self, source: IntegrationSource) -> dict[str, Any]:
        config = self._config_for(source)
        if config is None:
            return {
                "documents": [],
                "events": [],
                "cost_lines": [],
                "activities": [],
                "errors": ["dynamic connector config not found or disabled"],
            }
        with self._client(config) as client:
            result: dict[str, Any] = {
                "documents": [],
                "events": [],
                "cost_lines": [],
                "activities": [],
                "errors": [],
            }
            cursor: str | None = None
            for page in range(100):
                params = self._page_params(config, page)
                pagination = config.pagination or {}
                if pagination.get("type") == "cursor" and cursor:
                    params[pagination.get("cursor_param", "cursor")] = cursor
                try:
                    resp = client.get("/", params=params)
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as exc:
                    result["errors"].append(f"fetch failed on page {page}: {exc}")
                    break

                page_items: dict[str, list[dict[str, Any]]] = {}
                any_items = False
                for kind in ("documents", "events", "cost_lines", "activities"):
                    items = self._collect_mapped(config, kind, data)
                    page_items[kind] = items
                    result[kind].extend(items)
                    if items:
                        any_items = True

                ptype = pagination.get("type", "none")
                if ptype == "none":
                    break
                if ptype == "offset" and not any_items:
                    break
                if ptype == "offset":
                    limit = pagination.get("limit", 100)
                    if sum(len(page_items[k]) for k in page_items) < limit:
                        break
                    continue
                if ptype == "cursor":
                    cursor = _resolve(data, pagination.get("cursor_path", ""))
                    if not cursor:
                        break
                    continue
            return result
