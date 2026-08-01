"""Change-owned tables (spec change §Data owned).

Events, sources, and confirmations are workspace-scoped (RLS). References to
baseline, findings, and ingestion data use UUIDs only — no cross-module FKs.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, WorkspaceScopedMixin


class ChangeEvent(Base, WorkspaceScopedMixin):
    _tablename_ = "change_events"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    baseline_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="candidate")
    title: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False, default="other")
    affected_scope: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence_band: Mapped[str] = mapped_column(String, nullable=False, default="medium")
    notice_type: Mapped[str | None] = mapped_column(String, nullable=True)
    trigger_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notice_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    notice_deadline_detail: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    impact_links: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ChangeSource(Base, WorkspaceScopedMixin):
    _tablename_ = "change_sources"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    change_event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("change_events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_kind: Mapped[str] = mapped_column(String, nullable=False, default="manual")
    document_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_quote: Mapped[str | None] = mapped_column(String, nullable=True)
    external_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    text_preview: Mapped[str | None] = mapped_column(String, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String, nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ChangeConfirmation(Base, WorkspaceScopedMixin):
    _tablename_ = "change_confirmations"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    change_event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("change_events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    confirmed_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    evidence_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
