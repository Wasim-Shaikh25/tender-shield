"""Employer Behaviour Graph reference tables (TS-196).

Non-tenant, OCDS-shaped harvest storage. No `workspace_id` — these tables hold
public procurement reference data only and must never receive customer data.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class MdEmployer(Base):
    __tablename__ = "md_employers"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    family: Mapped[str] = mapped_column(String, nullable=False, index=True)
    division: Mapped[str | None] = mapped_column(String, nullable=True)
    region: Mapped[str | None] = mapped_column(String, nullable=True)
    aliases: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    confidence: Mapped[str] = mapped_column(String, nullable=False, default="unresolved")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MdTender(Base):
    __tablename__ = "md_tenders"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ocid: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    source_id: Mapped[str] = mapped_column(String, nullable=False, default="")
    source_url: Mapped[str] = mapped_column(String, nullable=False, default="")
    buyer_name: Mapped[str] = mapped_column(String, nullable=False, default="")
    employer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, nullable=True, index=True
    )
    classification: Mapped[str] = mapped_column(String, nullable=False, default="")
    value_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")
    tender_start: Mapped[str | None] = mapped_column(String, nullable=True)
    tender_end: Mapped[str | None] = mapped_column(String, nullable=True)
    adapter_name: Mapped[str] = mapped_column(String, nullable=False, default="")
    adapter_version: Mapped[str] = mapped_column(String, nullable=False, default="")
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    raw_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class MdAward(Base):
    __tablename__ = "md_awards"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tender_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    ocid: Mapped[str] = mapped_column(String, nullable=False, index=True)
    winner: Mapped[str] = mapped_column(String, nullable=False, default="")
    value_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")
    bidder_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    award_date: Mapped[str | None] = mapped_column(String, nullable=True)
    source_url: Mapped[str] = mapped_column(String, nullable=False, default="")
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MdProfile(Base):
    __tablename__ = "md_profiles"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    employer_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    family: Mapped[str] = mapped_column(String, nullable=False, index=True)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    aggregates: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MdHarvestRun(Base):
    __tablename__ = "md_harvest_runs"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String, nullable=False)
    adapter_name: Mapped[str] = mapped_column(String, nullable=False, default="")
    adapter_version: Mapped[str] = mapped_column(String, nullable=False, default="")
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    counts: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    errors: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
