"""Base connector interface for live CDE/ERP sync (TS-333)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.modules.integrations.models import IntegrationSource


class BaseConnector(ABC):
    name: str = ""
    auth_required: bool = True

    @abstractmethod
    def authorization_url(
        self, source: IntegrationSource, redirect_uri: str, state: str
    ) -> str | None:
        ...

    @abstractmethod
    def exchange_code(
        self, source: IntegrationSource, code: str, redirect_uri: str
    ) -> dict[str, Any]:
        ...

    @abstractmethod
    def fetch(self, source: IntegrationSource) -> dict[str, Any]:
        """Return normalized import shape: documents, events, cost_lines, activities."""
        ...
