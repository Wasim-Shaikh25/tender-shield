"""Rulepacks-owned tables (TS-218 correction proposals, TS-348 rulepack admin)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, WorkspaceScopedMixin


class RulePack(Base):
    """A runtime-uploaded rulepack. Built-in disk packs remain authoritative
    and are loaded by `RulePackLoader` when no DB version is active.

    `workspace_id` is NULL for global packs (visible to all workspaces); scoped
    packs are private to the owning workspace.
    """

    __tablename__ = "rulepacks"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    pack_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[str] = mapped_column(String, nullable=False)
    scope: Mapped[str] = mapped_column(
        String, nullable=False, default="workspace", index=True
    )  # "global" or "workspace"
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    jurisdiction: Mapped[str] = mapped_column(String, nullable=False, default="IN")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="draft"
    )  # draft | active | deprecated
    meta: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RulePackFile(Base):
    """Source files (PDF/Word/image/etc.) attached to an uploaded rulepack."""

    __tablename__ = "rulepack_files"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    rulepack_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("rulepacks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    path: Mapped[str] = mapped_column(String, nullable=False)
    storage_key: Mapped[str] = mapped_column(String, nullable=False)
    mime_type: Mapped[str] = mapped_column(
        String, nullable=False, default="application/octet-stream"
    )
    size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    checksum: Mapped[str] = mapped_column(String, nullable=False, default="")
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OpportunityRulepack(Base, WorkspaceScopedMixin):
    """Many-to-many link between an opportunity and the rulepacks applied to it."""

    _tablename_ = "opportunity_rulepacks"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rulepack_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("rulepacks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    applied_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


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
