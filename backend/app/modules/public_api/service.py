"""Public API + e-signature service (TS-292)."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.public_api.models import PublicApiKey, PublicSignatureRequest


class PublicApiError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _hash_key(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class PublicApiService:
    def __init__(
        self,
        session: Session,
        *,
        change_factory: Callable[[Session], object] | None = None,
        publish: Callable[[str, dict], Any] | None = None,
    ) -> None:
        self.s = session
        self._change_factory = change_factory
        self._publish = publish or (lambda event, payload: None)

    def create_key(
        self,
        workspace_id,
        created_by,
        *,
        name: str,
        scopes: list[str] | None = None,
    ) -> tuple[PublicApiKey, str]:
        token = secrets.token_urlsafe(32)
        row = PublicApiKey(
            workspace_id=uuid.UUID(str(workspace_id)),
            name=name,
            key_hash=_hash_key(token),
            scopes=scopes or ["read"],
            created_by=uuid.UUID(str(created_by)),
        )
        self.s.add(row)
        self.s.commit()
        self.s.refresh(row)
        return row, token

    def list_keys(self, workspace_id) -> list[PublicApiKey]:
        return list(
            self.s.scalars(
                select(PublicApiKey).where(
                    PublicApiKey.workspace_id == uuid.UUID(str(workspace_id)),
                    PublicApiKey.revoked_at.is_(None),
                )
            )
        )

    def authenticate(self, token: str | None) -> dict | None:
        if not token:
            return None
        hash_value = _hash_key(token)
        row = self.s.scalar(
            select(PublicApiKey).where(
                PublicApiKey.key_hash == hash_value,
                PublicApiKey.revoked_at.is_(None),
            )
        )
        if row is None:
            return None
        row.last_used_at = datetime.now(UTC)
        self.s.commit()
        return {
            "workspace_id": str(row.workspace_id),
            "scopes": row.scopes or [],
        }

    def request_signature(
        self,
        workspace_id,
        opportunity_id,
        *,
        recipient_email: str,
        notice_id: str | None = None,
        change_event_id: str | None = None,
        provider: str = "docusign_stub",
    ) -> PublicSignatureRequest:
        external_id = secrets.token_urlsafe(16)
        row = PublicSignatureRequest(
            workspace_id=uuid.UUID(str(workspace_id)),
            opportunity_id=uuid.UUID(str(opportunity_id)),
            notice_id=uuid.UUID(str(notice_id)) if notice_id else None,
            change_event_id=uuid.UUID(str(change_event_id)) if change_event_id else None,
            recipient_email=recipient_email,
            provider=provider,
            external_id=external_id,
            status="requested",
        )
        self.s.add(row)
        self.s.commit()
        self.s.refresh(row)
        self._publish(
            "public_api.signature_requested",
            {
                "workspace_id": str(workspace_id),
                "request_id": str(row.id),
                "opportunity_id": str(opportunity_id),
                "external_id": external_id,
            },
        )
        return row

    def signature_callback(self, external_id: str, status: str) -> PublicSignatureRequest:
        row = self.s.scalar(
            select(PublicSignatureRequest).where(
                PublicSignatureRequest.external_id == external_id,
            )
        )
        if row is None:
            raise PublicApiError("not_found")
        row.status = status
        if status == "signed":
            row.signed_at = datetime.now(UTC)
        self.s.commit()
        self.s.refresh(row)
        return row

    def get_signature_status(self, workspace_id, request_id) -> PublicSignatureRequest:
        row = self.s.scalar(
            select(PublicSignatureRequest).where(
                PublicSignatureRequest.id == uuid.UUID(str(request_id)),
                PublicSignatureRequest.workspace_id == uuid.UUID(str(workspace_id)),
            )
        )
        if row is None:
            raise PublicApiError("not_found")
        return row
