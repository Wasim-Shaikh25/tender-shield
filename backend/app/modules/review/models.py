"""Review-owned tables. `audit_log` is append-only (Doc §3.2, §11.4): the code
only ever INSERTs; in production the DB role has no UPDATE/DELETE grant on it."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, WorkspaceScopedMixin

# BIGSERIAL on Postgres; plain INTEGER on SQLite (the only rowid alias that
# autoincrements there).
_BigId = BigInteger().with_variant(Integer, "sqlite")


class AuditLog(Base, WorkspaceScopedMixin):
    _tablename_ = "audit_log"
    id: Mapped[int] = mapped_column(_BigId, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    object_type: Mapped[str | None] = mapped_column(String, nullable=True)
    object_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
