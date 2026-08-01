"""Process notice-deadline countdown alerts (TS-252)."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.modules.change.models import ChangeEvent, ChangeNoticeAlertLog
from app.modules.change.notice_alerts import alert_bucket_for_deadline


def _already_sent(
    session: Session, workspace_id: str, user_id: str, event_id: str, alert_day: int
) -> bool:
    return (
        session.scalar(
            select(
                exists().where(
                    ChangeNoticeAlertLog.workspace_id == uuid.UUID(str(workspace_id)),
                    ChangeNoticeAlertLog.user_id == uuid.UUID(str(user_id)),
                    ChangeNoticeAlertLog.change_event_id == uuid.UUID(str(event_id)),
                    ChangeNoticeAlertLog.alert_day == alert_day,
                )
            )
        )
        or False
    )


def _record_sent(
    session: Session,
    workspace_id: str,
    user_id: str,
    opportunity_id: str,
    event_id: str,
    alert_day: int,
) -> None:
    session.add(
        ChangeNoticeAlertLog(
            workspace_id=uuid.UUID(str(workspace_id)),
            user_id=uuid.UUID(str(user_id)),
            opportunity_id=uuid.UUID(str(opportunity_id)),
            change_event_id=uuid.UUID(str(event_id)),
            alert_day=alert_day,
        )
    )
    session.commit()


def process_notice_alerts(
    session: Session,
    *,
    workspace_factory,
    send_email,
    preference_fn,
) -> int:
    """Scan confirmed change events with notice deadlines and send deduped alerts."""
    if workspace_factory is None or send_email is None or preference_fn is None:
        return 0

    sent = 0
    admin = workspace_factory(session)
    for workspace in admin.list_all_workspaces():
        workspace_id = workspace["workspace_id"]
        from app.core.db import bind_workspace_context

        bind_workspace_context(session, workspace_id)
        events = session.scalars(
            select(ChangeEvent).where(
                ChangeEvent.workspace_id == uuid.UUID(str(workspace_id)),
                ChangeEvent.status == "confirmed",
                ChangeEvent.notice_deadline.is_not(None),
            )
        ).all()
        for event in events:
            deadline: date | None = event.notice_deadline
            if deadline is None:
                continue
            bucket = alert_bucket_for_deadline(deadline)
            if bucket is None:
                continue
            for member in admin.list_members(workspace_id):
                user_id = member["user_id"]
                pref = preference_fn(session, user_id)
                if not pref.email_deadlines:
                    continue
                event_id = str(event.id)
                if _already_sent(session, workspace_id, user_id, event_id, bucket):
                    continue
                send_email(
                    member["email"],
                    f"Notice deadline alert: {event.title}",
                    (
                        f"Change event '{event.title}' has a notice deadline on "
                        f"{deadline.isoformat()} ({bucket} day alert)."
                    ),
                )
                _record_sent(
                    session,
                    workspace_id,
                    user_id,
                    str(event.opportunity_id),
                    event_id,
                    bucket,
                )
                sent += 1
    return sent
