"""Express anti-abuse guards (TS-214)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.express.errors import ExpressError
from app.modules.express.models import ExDocument, ExSession

MAX_SESSIONS_PER_EMAIL_PER_DAY = 5
MAX_SESSIONS_PER_IP_PER_DAY = 20
MAX_TEASERS_PER_IP_PER_DAY = 10

_TEASER_STATES = ("teaser_ready", "checkout_pending", "purchased", "claimed")


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _since(days: float = 1.0) -> datetime:
    return _utc_now() - timedelta(days=days)


def check_session_create(session: Session, *, email: str, client_ip: str | None) -> None:
    email = email.strip().lower()
    since = _since()
    email_count = session.scalar(
        select(func.count())
        .select_from(ExSession)
        .where(ExSession.email == email, ExSession.created_at >= since)
    )
    if email_count and email_count >= MAX_SESSIONS_PER_EMAIL_PER_DAY:
        raise ExpressError("rate_limit_email")
    if client_ip:
        ip_count = session.scalar(
            select(func.count())
            .select_from(ExSession)
            .where(ExSession.client_ip == client_ip, ExSession.created_at >= since)
        )
        if ip_count and ip_count >= MAX_SESSIONS_PER_IP_PER_DAY:
            raise ExpressError("rate_limit_ip")


def check_teaser_ip_cap(session: Session, *, client_ip: str | None) -> None:
    if not client_ip:
        return
    since = _since()
    count = session.scalar(
        select(func.count())
        .select_from(ExSession)
        .where(
            ExSession.client_ip == client_ip,
            ExSession.state.in_(_TEASER_STATES),
            ExSession.created_at >= since,
        )
    )
    if count and count >= MAX_TEASERS_PER_IP_PER_DAY:
        raise ExpressError("rate_limit_teaser")


def check_teaser_document_dedupe(session: Session, *, session_id, doc_hashes: list[str]) -> None:
    for digest in doc_hashes:
        if not digest:
            continue
        existing = session.scalar(
            select(ExDocument.id)
            .join(ExSession, ExDocument.session_id == ExSession.id)
            .where(
                ExDocument.sha256 == digest,
                ExSession.id != session_id,
                ExSession.state.in_(_TEASER_STATES),
            )
            .limit(1)
        )
        if existing is not None:
            raise ExpressError("teaser_duplicate")
