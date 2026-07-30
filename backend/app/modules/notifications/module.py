import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import bind_workspace_context
from app.core.module import AppContext, ModuleSpec
from app.modules.notifications import models  # noqa: F401 - register tables
from app.modules.notifications.adapters import build_sender
from app.modules.notifications.models import DeadlineAlertLog, NotificationPreference
from app.modules.notifications.router import router
from app.modules.notifications.sender import Message

logger = logging.getLogger(__name__)

# Alerts are sent at these "days before deadline" buckets.
_ALERT_BUCKETS = (7, 3, 1, 0)


def _alert_day(due_at: datetime) -> int | None:
    """Return the alert bucket for a due deadline, or None if outside alert window."""
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=UTC)
    delta = due_at - datetime.now(UTC)
    days = delta.days
    if days < 0:
        return None
    candidates = [bucket for bucket in _ALERT_BUCKETS if days <= bucket]
    return min(candidates) if candidates else None


def _preference(session: Session, user_id: str) -> NotificationPreference:
    uid = uuid.UUID(str(user_id))
    pref = session.get(NotificationPreference, uid)
    if pref is None:
        pref = NotificationPreference(
            user_id=uid,
            email_deadlines=True,
            sms_deadlines=False,
            email_digest=True,
            sms_alerts=False,
            marketing=False,
        )
        session.add(pref)
    return pref


def _already_sent(
    session: Session, workspace_id: str, user_id: str, deadline_id: str, alert_day: int
) -> bool:
    from sqlalchemy import exists

    return (
        session.scalar(
            select(
                exists().where(
                    DeadlineAlertLog.workspace_id == uuid.UUID(str(workspace_id)),
                    DeadlineAlertLog.user_id == uuid.UUID(str(user_id)),
                    DeadlineAlertLog.deadline_id == uuid.UUID(str(deadline_id)),
                    DeadlineAlertLog.alert_day == alert_day,
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
    deadline_id: str,
    alert_day: int,
) -> None:
    session.add(
        DeadlineAlertLog(
            workspace_id=uuid.UUID(str(workspace_id)),
            user_id=uuid.UUID(str(user_id)),
            opportunity_id=uuid.UUID(str(opportunity_id)),
            deadline_id=uuid.UUID(str(deadline_id)),
            alert_day=alert_day,
        )
    )
    session.commit()


def setup(ctx: AppContext) -> None:
    # ConsoleSender in dev/test; SES/MSG91 adapters register when credentials are set.
    sender = build_sender(ctx.settings)
    ctx.registry.provide("notifications.sender", sender)

    scheduler = ctx.registry.get("core.scheduler")
    if scheduler is not None:

        def _deadline_alert_tick() -> None:
            """Scan workspaces for upcoming deadlines and alert members once per bucket."""
            if ctx.settings.redis_url:
                import redis

                redis_client = redis.Redis.from_url(ctx.settings.redis_url, decode_responses=True)
                lock = redis_client.lock(
                    "tendershield:deadline_alert_lock",
                    timeout=60 * 60 * 23,
                    blocking_timeout=5,
                )
                if not lock.acquire():
                    logger.info("deadline_alert_tick skipped, another instance holds the lock")
                    return
            else:
                lock = None

            try:
                session_maker = ctx.registry.get("db.sessionmaker")
                ingestion_factory = ctx.registry.get("ingestion.service_factory")
                workspace_factory = ctx.registry.get("auth.workspace_factory")
                if not session_maker or not ingestion_factory or not workspace_factory:
                    return

                session = session_maker()
                try:
                    admin = workspace_factory(session)
                    for workspace in admin.list_all_workspaces():
                        workspace_id = workspace["workspace_id"]
                        bind_workspace_context(session, workspace_id)
                        ingestion = ingestion_factory(session)
                        for opp in ingestion.list_opportunities(workspace_id):
                            for dl in ingestion.list_deadlines(workspace_id, str(opp.id)):
                                due_at = dl.due_at
                                if not due_at or dl.confirmed:
                                    continue
                                bucket = _alert_day(due_at)
                                if bucket is None:
                                    continue
                                for member in admin.list_members(workspace_id):
                                    user_id = member["user_id"]
                                    pref = _preference(session, user_id)
                                    if not pref.email_deadlines:
                                        continue
                                    if _already_sent(
                                        session, workspace_id, user_id, str(dl.id), bucket
                                    ):
                                        continue
                                    sender.send(
                                        Message(
                                            channel="email",
                                            to=member["email"],
                                            subject=f"Deadline alert: {opp.title}",
                                            body=(
                                                f"Deadline '{dl.description or dl.kind}' "
                                                f"is due at {due_at.isoformat()} "
                                                f"for opportunity {str(opp.id)}."
                                            ),
                                        )
                                    )
                                    _record_sent(
                                        session,
                                        workspace_id,
                                        user_id,
                                        str(opp.id),
                                        str(dl.id),
                                        bucket,
                                    )
                finally:
                    session.close()
            finally:
                if lock:
                    try:
                        lock.release()
                    except Exception:
                        pass

        scheduler.add_job(_deadline_alert_tick, "interval", hours=24)


module = ModuleSpec(
    name="notifications",
    version="0.1.0",
    router=router,
    soft_deps=("ingestion", "auth"),
    setup=setup,
)
