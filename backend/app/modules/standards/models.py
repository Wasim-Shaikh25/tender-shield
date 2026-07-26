"""standards-owned table (org-scoped, RLS). One row per org holds that firm's
custom notice standard: a merge mode + a list of notice categories (same shape
as a rule-pack NoticeCategory). Org data, not filesystem pack data."""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import JSON, DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, OrgScopedMixin


class OrgNoticeStandard(Base, OrgScopedMixin):
    _tablename_ = "org_notice_standards"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # "prevail"  → org categories override the rule-pack standard by key.
    # "side_by_side" → org categories are shown alongside (never override).
    mode: Mapped[str] = mapped_column(String, nullable=False, default="prevail")
    categories: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class OrgCommercialStandard(Base, OrgScopedMixin):
    _tablename_ = "org_commercial_standards"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    operator: Mapped[str] = mapped_column(String, nullable=False, default="gt")
    threshold: Mapped[float] = mapped_column(sa.Numeric(12, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String, nullable=False, default="percent")
    applies_to: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
