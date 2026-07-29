"""baseline-owned table (Doc §3.2 extension). A sealed baseline is an immutable,
hash-sealed snapshot of the reviewed commercial state at a point in time. Rows
are append-only: a re-freeze inserts a new version, never mutates an existing
one (spec baseline B3). Workspace-scoped (RLS)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, WorkspaceScopedMixin


class Baseline(Base, WorkspaceScopedMixin):
    _tablename_ = "baselines"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    # "tender" (the bid we reviewed) | "award" (state at award, after negotiation).
    source: Mapped[str] = mapped_column(String, nullable=False, default="tender")
    # SHA-256 over the canonical snapshot JSON (excludes sealed_at) — the seal.
    content_sha256: Mapped[str] = mapped_column(String, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    sealed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    sealed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AwardDocument(Base, WorkspaceScopedMixin):
    _tablename_ = "award_documents"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str] = mapped_column(String, nullable=False, default="")
    sha256: Mapped[str] = mapped_column(String, nullable=False, default="")
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
