"""Express lane tables (TS-208 scaffold, spec §Data owned)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, WorkspaceScopedMixin


class ExSession(Base, WorkspaceScopedMixin):
    """Anonymous analysis session backed by an ephemeral internal workspace."""

    __tablename__ = "ex_sessions"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    token: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    email: Mapped[str] = mapped_column(String, nullable=False)
    tier: Mapped[str] = mapped_column(String, nullable=False, default="snapshot")
    state: Mapped[str] = mapped_column(String, nullable=False, default="created")
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    acknowledgment: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    acknowledgment_version: Mapped[str] = mapped_column(String, nullable=False, default="")
    client_ip: Mapped[str | None] = mapped_column(String, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ExPurchase(Base, WorkspaceScopedMixin):
    __tablename__ = "ex_purchases"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    provider_order_id: Mapped[str] = mapped_column(String, nullable=False, default="")
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ExDocument(Base, WorkspaceScopedMixin):
    __tablename__ = "ex_documents"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String, nullable=False, default="")
    sha256: Mapped[str] = mapped_column(String, nullable=False, default="")
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
