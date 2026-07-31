"""Express lane service scaffold (TS-208)."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.modules.express.models import ExSession

DEFAULT_TTL_HOURS = 72


class ExpressService:
    def __init__(self, session: Session):
        self.s = session

    def create_session(
        self,
        *,
        email: str,
        tier: str = "snapshot",
        acknowledgment: dict | None = None,
        workspace_id,
        ttl_hours: int = DEFAULT_TTL_HOURS,
    ) -> ExSession:
        row = ExSession(
            workspace_id=uuid.UUID(str(workspace_id)),
            token=secrets.token_urlsafe(32),
            email=email,
            tier=tier,
            state="created",
            acknowledgment=acknowledgment or {},
            expires_at=datetime.now(UTC) + timedelta(hours=ttl_hours),
        )
        self.s.add(row)
        self.s.commit()
        self.s.refresh(row)
        return row

    def get_by_token(self, token: str) -> ExSession | None:
        from sqlalchemy import select

        return self.s.scalar(select(ExSession).where(ExSession.token == token))
