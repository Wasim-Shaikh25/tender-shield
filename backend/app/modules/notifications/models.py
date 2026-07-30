"""Notification preferences and alert log (Doc §11.6/§11.7).

- `NotificationPreference` is account-level (one row per user).
- `DeadlineAlertLog` is workspace-scoped so RLS can isolate alert state per tenant.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.db import Base, WorkspaceScopedMixin


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, nullable=False)
    email_deadlines: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sms_deadlines: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_digest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sms_alerts: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    marketing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    quiet_hours_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quiet_hours_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class DeadlineAlertLog(Base, WorkspaceScopedMixin):
    _tablename_ = "deadline_alert_log"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    deadline_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    alert_day: Mapped[int] = mapped_column(Integer, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (UniqueConstraint("user_id", "deadline_id", "alert_day"),)
