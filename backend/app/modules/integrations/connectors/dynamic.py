"""Generic dynamic REST connector (TS-334, TS-336).

Reads connector configuration from the DB at runtime so non-technical users can
point TenderShield at any JSON REST API (ERP sandbox, Oracle, custom systems).
No generated code is stored or executed.

SSRFA protection: base_url is validated against private/reserved networks and
non-HTTP(S) schemes before any outbound request is made.
"""

from __future__ import annotations

import ipaddress
import socket
import urllib.parse
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import object_session

from app.modules.integrations.connectors.base import BaseConnector
from app.modules.integrations.models import DynamicConnectorConfig, IntegrationSource


class DynamicConnectorError(Exception):
    """Raised when dynamic connector configuration is unsafe or unusable."""


_ALLOWED_SCHEMES = {"http", "https"}

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("255.255.255.255/32"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("::ffff:127.0.0.0/104"),
    ipaddress.ip_network("::ffff:10.0.0.0/104"),
    ipaddress.ip_network("::ffff:172.16.0.0/108"),
    ipaddress.ip_network("::ffff:192.168.0.0/112"),
    ipaddress.ip_network("::ffff:169.254.0.0/112"),
]


def _is_blocked_address(addr: str) -> bool:
    """Return True if the address is loopback, link-local, private, multicast,
    reserved, or otherwise not safe for a server-side request."""
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    if (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_private
        or ip.is_reserved
        or ip.is_unspecified
    ):
        return True
    for net in _BLOCKED_NETWORKS:
        if ip in net:
            return True
    return False


def _resolve_host_ips(host: str) -> set[str]:
    """Return all IP addresses a hostname resolves to."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return set()
    return {str(info[4][0]) for info in infos}


def validate_url(url: str | None) -> None:
    """Validate a dynamic connector base_url for SSRF safety.

    Raises DynamicConnectorError if the URL is missing, uses an unsafe scheme,
    contains credentials, or resolves to a blocked address.
    """
    if not url or not isinstance(url, str):
        raise DynamicConnectorError("invalid_url")
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError as exc:
        raise DynamicConnectorError("invalid_url") from exc
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise DynamicConnectorError("invalid_url")
    if not parsed.netloc or parsed.username is not None or parsed.password is not None:
        raise DynamicConnectorError("invalid_url")
    host = parsed.hostname
    if not host:
        raise DynamicConnectorError("invalid_url")
    if _is_blocked_address(host):
        raise DynamicConnectorError("invalid_url")
    for addr in _resolve_host_ips(host):
        if _is_blocked_address(addr):
            raise DynamicConnectorError("invalid_url")


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
                DynamicConnectorConfig.id == config_id,
                DynamicConnectorConfig.enabled == True,  # noqa: E712
            )
        )

    def _client(self, config: DynamicConnectorConfig) -> httpx.Client:
        validate_url(config.base_url)
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
