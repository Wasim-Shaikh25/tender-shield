"""Notification preference routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import current_principal, get_session
from app.modules.notifications.service import NotificationService

router = APIRouter()


class NotificationPreferenceBody(BaseModel):
    email_deadlines: bool | None = None
    sms_deadlines: bool | None = None
    email_digest: bool | None = None
    sms_alerts: bool | None = None
    marketing: bool | None = None
    quiet_hours_start: int | None = None
    quiet_hours_end: int | None = None


class NotificationPreferenceResponse(BaseModel):
    email_deadlines: bool
    sms_deadlines: bool
    email_digest: bool
    sms_alerts: bool
    marketing: bool
    quiet_hours_start: int | None
    quiet_hours_end: int | None


def _to_response(pref):
    return {
        "email_deadlines": pref.email_deadlines,
        "sms_deadlines": pref.sms_deadlines,
        "email_digest": pref.email_digest,
        "sms_alerts": pref.sms_alerts,
        "marketing": pref.marketing,
        "quiet_hours_start": pref.quiet_hours_start,
        "quiet_hours_end": pref.quiet_hours_end,
    }


@router.get("/preferences", response_model=NotificationPreferenceResponse)
def get_preferences(
    session: Session = Depends(get_session),
    principal=Depends(current_principal),
):
    pref = NotificationService(session).get_preferences(principal.user_id)
    return _to_response(pref)


@router.put("/preferences", response_model=NotificationPreferenceResponse)
def update_preferences(
    body: NotificationPreferenceBody,
    session: Session = Depends(get_session),
    principal=Depends(current_principal),
):
    pref = NotificationService(session).update_preferences(
        principal.user_id, body.model_dump(exclude_none=True)
    )
    return _to_response(pref)
