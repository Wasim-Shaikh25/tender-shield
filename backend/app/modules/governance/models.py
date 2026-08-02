"""Governance-owned tables (TS-332)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, WorkspaceScopedMixin


class WorkspaceDataGovernance(Base, WorkspaceScopedMixin):
    _tablename_ = "workspace_data_governance"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    data_region: Mapped[str] = mapped_column(String, nullable=False, default="")
    retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    archive_after_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    legal_hold: Mapped[bool] = mapped_column(default=False, nullable=False)
    encryption_at_rest: Mapped[str] = mapped_column(
        String, nullable=False, default="none"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("workspace_id"),
    )
