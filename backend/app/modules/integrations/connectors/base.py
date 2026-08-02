"""Base connector interface for live CDE/ERP sync (TS-333, TS-337)."""

from __future__ import annotations

import hmac
from abc import ABC, abstractmethod
from hashlib import sha256
from typing import Any

from app.modules.integrations.models import IntegrationSource


class BaseConnector(ABC):
    name: str = ""
    auth_required: bool = True
    webhook_signature_header: str = "X-Integration-Signature"

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

    def verify_webhook(
        self,
        source: IntegrationSource,
        raw_body: bytes,
        signature: str | None,
        secret: str | None,
    ) -> bool:
        """Verify a webhook signature.

        Default implementation requires an HMAC-SHA256 hex digest of the raw
        request body using the source's webhook_secret. Connectors with provider-
        specific signing (Procore, Autodesk, Aconex, etc.) can override this.
        """
        if not signature or not secret:
            return False
        expected = hmac.new(
            secret.encode("utf-8"), raw_body, sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
