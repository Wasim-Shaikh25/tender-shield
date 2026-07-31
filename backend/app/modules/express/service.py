"""Express lane service (TS-208/209)."""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.express.models import ExDocument, ExSession

DEFAULT_TTL_HOURS = 72
EXPRESS_MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ACKNOWLEDGMENT_VERSION = "express-unreviewed-v1"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


class ExpressError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class ExpressService:
    def __init__(
        self,
        session: Session,
        *,
        create_workspace: Callable | None = None,
    ):
        self.s = session
        self._create_workspace = create_workspace

    def create_session(
        self,
        *,
        email: str,
        tier: str = "snapshot",
        acknowledgment: dict | None = None,
        acknowledgment_version: str = ACKNOWLEDGMENT_VERSION,
        client_ip: str | None = None,
        ttl_hours: int = DEFAULT_TTL_HOURS,
    ) -> ExSession:
        if not acknowledgment or not acknowledgment.get("accepted"):
            raise ExpressError("acknowledgment_required")
        if self._create_workspace is None:
            raise ExpressError("workspace_unavailable")
        workspace_id = self._create_workspace(self.s, label="express")
        row = ExSession(
            workspace_id=workspace_id,
            token=secrets.token_urlsafe(32),
            email=email.strip().lower(),
            tier=tier,
            state="created",
            acknowledgment=acknowledgment,
            acknowledgment_version=acknowledgment_version,
            client_ip=client_ip,
            expires_at=_utc_now() + timedelta(hours=ttl_hours),
        )
        self.s.add(row)
        self.s.commit()
        self.s.refresh(row)
        return row

    def get_by_token(self, token: str) -> ExSession | None:
        row = self.s.scalar(select(ExSession).where(ExSession.token == token))
        if row is None:
            return None
        if row.expires_at and _as_utc(row.expires_at) < _utc_now():
            row.state = "expired"
            self.s.commit()
            return None
        return row

    def require_session(self, token: str) -> ExSession:
        row = self.get_by_token(token)
        if row is None:
            raise ExpressError("session_not_found")
        return row

    def upload_document(
        self,
        token: str,
        *,
        filename: str,
        data: bytes,
        retention_days: int = 90,
    ) -> ExDocument:
        if len(data) > EXPRESS_MAX_UPLOAD_BYTES:
            raise ExpressError("upload_too_large")
        session = self.require_session(token)
        doc = ExDocument(
            workspace_id=session.workspace_id,
            session_id=session.id,
            filename=filename,
            sha256=hashlib.sha256(data).hexdigest(),
            retention_until=_utc_now() + timedelta(days=retention_days),
        )
        session.state = "uploaded"
        self.s.add(doc)
        self.s.commit()
        self.s.refresh(doc)
        return doc
