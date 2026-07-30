"""Notification preferences service."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.modules.notifications.models import NotificationPreference


class NotificationService:
    def __init__(self, session: Session):
        self.s = session

    def get_preferences(self, user_id) -> NotificationPreference:
        uid = uuid.UUID(str(user_id))
        pref = self.s.get(NotificationPreference, uid)
        if pref is None:
            pref = NotificationPreference(user_id=uid)
            self.s.add(pref)
            self.s.commit()
        return pref

    def update_preferences(self, user_id, settings: dict) -> NotificationPreference:
        pref = self.get_preferences(user_id)
        for field in (
            "email_deadlines",
            "sms_deadlines",
            "email_digest",
            "sms_alerts",
            "marketing",
            "quiet_hours_start",
            "quiet_hours_end",
        ):
            if field in settings:
                value = settings[field]
                if value is not None and field in ("quiet_hours_start", "quiet_hours_end"):
                    value = int(value)
                setattr(pref, field, value)
        self.s.commit()
        return pref
