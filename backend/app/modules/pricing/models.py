"""`pi_loadings`, `pi_rate_matches`, `pi_cashflow_runs` (TS-201, spec §Data owned).

Workspace-scoped like every other table (RLS, `CLAUDE.md` §4). Money is minor
units + an explicit currency column throughout — no table in this module ever
stores a float amount."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Float, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, WorkspaceScopedMixin


class PiLoading(Base, WorkspaceScopedMixin):
    _tablename_ = "pi_loadings"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    finding_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    pattern_id: Mapped[str] = mapped_column(String, nullable=False)
    produced: Mapped[bool] = mapped_column(nullable=False, default=False)
    amount_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")
    basis: Mapped[str | None] = mapped_column(String, nullable=True)
    formula: Mapped[str | None] = mapped_column(String, nullable=True)
    rulepack_version: Mapped[str] = mapped_column(String, nullable=False)
    inputs_used: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    missing_inputs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PiRateMatch(Base, WorkspaceScopedMixin):
    _tablename_ = "pi_rate_matches"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    src_row: Mapped[int] = mapped_column(Integer, nullable=False)
    boq_description: Mapped[str] = mapped_column(String, nullable=False, default="")
    boq_unit: Mapped[str] = mapped_column(String, nullable=False, default="")
    boq_rate_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    matched_by: Mapped[str] = mapped_column(String, nullable=False)  # code|description|unmatched
    schedule_id: Mapped[str | None] = mapped_column(String, nullable=True)
    schedule_code: Mapped[str | None] = mapped_column(String, nullable=True)
    schedule_description: Mapped[str | None] = mapped_column(String, nullable=True)
    schedule_rate_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    variance_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    variance_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PiCashflowRun(Base, WorkspaceScopedMixin):
    _tablename_ = "pi_cashflow_runs"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    inputs: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    assumptions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    monthly: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    peak_requirement_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    peak_month: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_financing_cost_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
