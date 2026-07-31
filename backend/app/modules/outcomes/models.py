"""Workspace-scoped outcome capture (TS-215, spec §Data owned)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, WorkspaceScopedMixin


class OcBidOutcome(Base, WorkspaceScopedMixin):
    _tablename_ = "oc_bid_outcomes"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    result: Mapped[str] = mapped_column(String, nullable=False)
    quoted_value_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    l1_value_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")
    bidder_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decline_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OcRiskMaterialization(Base, WorkspaceScopedMixin):
    _tablename_ = "oc_risk_materialization"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    finding_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    materialized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    impact_amount_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")
    narrative: Mapped[str | None] = mapped_column(String, nullable=True)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
