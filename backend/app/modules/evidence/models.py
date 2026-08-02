"""Evidence-owned tables (TS-254)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, WorkspaceScopedMixin


class EvidenceRecord(Base, WorkspaceScopedMixin):
    _tablename_ = "evidence_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    change_event_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    record_type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    document_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    custody_chain: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    record_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
