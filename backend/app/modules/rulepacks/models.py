"""Rulepacks-owned tables (TS-218 correction proposals)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, WorkspaceScopedMixin


class CorrectionProposal(Base, WorkspaceScopedMixin):
    """Proposed rulepack overlay from aggregated review corrections.

    Never auto-applied — a human approves or dismisses (Build Doc §2.4).
    """

    __tablename__ = "rp_correction_proposals"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    pack_id: Mapped[str] = mapped_column(String, nullable=False, default="in-works")
    pattern_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    employer_family: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="proposed")
    overlay: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    stats: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
