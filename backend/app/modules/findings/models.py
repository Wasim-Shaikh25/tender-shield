"""The shared `findings` table (Doc §3.2). One module owns the table; risk and
boq write to it via the published store capability, and review reads/updates the
review columns — none of them import this module."""

from __future__ import annotations

import uuid

from sqlalchemy import JSON, BigInteger, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, WorkspaceScopedMixin


class FindingRow(Base, WorkspaceScopedMixin):
    _tablename_ = "findings"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    # `producer` scopes idempotent re-runs (a risk re-run replaces only risk rows).
    producer: Mapped[str] = mapped_column(String, nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    detail: Mapped[str] = mapped_column(String, nullable=False, default="")
    source: Mapped[str] = mapped_column(String, nullable=False)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_quote: Mapped[str | None] = mapped_column(String, nullable=True)
    affected_trades: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    suggested_action: Mapped[str | None] = mapped_column(String, nullable=True)
    pattern_id: Mapped[str | None] = mapped_column(String, nullable=True)
    pattern_version: Mapped[str | None] = mapped_column(String, nullable=True)
    amount_exposure: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # review state (Doc §11.4) — driven by the review module later (TS-021).
    review_status: Mapped[str] = mapped_column(String, nullable=False, default="proposed")
    review_note: Mapped[str | None] = mapped_column(String, nullable=True)
    review_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    explanation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    disclaimer: Mapped[str | None] = mapped_column(String, nullable=True)
