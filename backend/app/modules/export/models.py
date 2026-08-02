"""Report-template storage for branded exports (TS-331).

A workspace may define one default template; the export service applies it to
generated DOCX / XLSX / PDF packs.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, WorkspaceScopedMixin


class ReportTemplate(Base, WorkspaceScopedMixin):
    __tablename__ = "report_templates"
    _tablename_ = "report_templates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False, default="Default")
    is_default: Mapped[bool] = mapped_column(default=False)
    primary_color: Mapped[str | None] = mapped_column(String, nullable=True)
    accent_color: Mapped[str | None] = mapped_column(String, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    watermark_text: Mapped[str | None] = mapped_column(String, nullable=True)
    footer_text: Mapped[str | None] = mapped_column(String, nullable=True)
    report_title: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
