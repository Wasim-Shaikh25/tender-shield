"""baseline-owned table (Doc §3.2 extension). A sealed baseline is an immutable,
hash-sealed snapshot of the reviewed commercial state at a point in time. Rows
are append-only: a re-freeze inserts a new version, never mutates an existing
one (spec baseline B3). Workspace-scoped (RLS)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid, func
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


class WatchlistControl(Base, WorkspaceScopedMixin):
    _tablename_ = "bl_watchlist_controls"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    baseline_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("baselines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    finding_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    obligation_key: Mapped[str] = mapped_column(String, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    trigger_text: Mapped[str | None] = mapped_column(String, nullable=True)
    review_cadence: Mapped[str] = mapped_column(String, nullable=False, default="monthly")
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_quote: Mapped[str | None] = mapped_column(String, nullable=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class NoticeContact(Base, WorkspaceScopedMixin):
    _tablename_ = "bl_notice_contacts"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "opportunity_id",
            "notice_type",
            name="uq_bl_notice_contacts_type",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    notice_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    party: Mapped[str] = mapped_column(String, nullable=False, default="employer")
    role_label: Mapped[str | None] = mapped_column(String, nullable=True)
    authorized_representative: Mapped[str | None] = mapped_column(String, nullable=True)
    postal_address: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    required_content: Mapped[list | None] = mapped_column(JSON, nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CostCode(Base, WorkspaceScopedMixin):
    _tablename_ = "bl_cost_codes"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "opportunity_id",
            "code",
            name="uq_bl_cost_codes_code",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    code: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    variation_category: Mapped[str | None] = mapped_column(String, nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CostCodeMapping(Base, WorkspaceScopedMixin):
    _tablename_ = "bl_cost_code_mappings"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cost_code_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("bl_cost_codes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    boq_src_row: Mapped[str | None] = mapped_column(String, nullable=True)
    finding_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    description_match: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
