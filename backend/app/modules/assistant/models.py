"""Assistant-owned tables (Doc §8). Conversation/session history lets users
return to a prior chat and audit what the assistant answered."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, WorkspaceScopedMixin


class ChatSession(Base, WorkspaceScopedMixin):
    _tablename_ = "chat_sessions"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ChatMessage(Base, WorkspaceScopedMixin):
    _tablename_ = "chat_messages"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String, nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(String, nullable=False)
    # message_type values: text | dashboard
    message_type: Mapped[str] = mapped_column(String, nullable=False, default="text")
    dashboard: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    grounded: Mapped[bool] = mapped_column(default=True, nullable=False)
    source: Mapped[str | None] = mapped_column(String, nullable=True)  # tool | llm | refusal
    citations: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
