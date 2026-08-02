"""Drawing register and title-block extraction models (TS-321, TS-322).

Workspace-scoped and org-isolated like every other tenant table (`CLAUDE.md` §4).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, WorkspaceScopedMixin


class Drawing(Base, WorkspaceScopedMixin):
    _tablename_ = "drawings"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    filename: Mapped[str] = mapped_column(String, nullable=False)
    drawing_number: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    revision: Mapped[str | None] = mapped_column(String, nullable=True)
    revision_date: Mapped[str | None] = mapped_column(String, nullable=True)
    discipline: Mapped[str | None] = mapped_column(String, nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("drawings.id", ondelete="SET NULL"), nullable=True, index=True
    )
    page_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True, server_default="0"
    )
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    title_block: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        String, nullable=False, server_default="current"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class DrawingComparison(Base, WorkspaceScopedMixin):
    _tablename_ = "drawing_comparisons"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    current_drawing_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("drawings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    previous_drawing_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("drawings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_pages: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    changed_regions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
