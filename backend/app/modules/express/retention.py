"""Express retention purge (TS-214)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.modules.express.models import ExDocument, ExSession


def _utc_now() -> datetime:
    return datetime.now(UTC)


def purge_expired(session: Session, *, now: datetime | None = None) -> dict:
    """Delete express documents past retention unless the session was claimed."""
    cutoff = now or _utc_now()
    doc_ids = list(
        session.scalars(
            select(ExDocument.id)
            .join(ExSession, ExDocument.session_id == ExSession.id)
            .where(
                ExDocument.retention_until.is_not(None),
                ExDocument.retention_until <= cutoff,
                ExSession.claimed_at.is_(None),
            )
        ).all()
    )
    if not doc_ids:
        return {"purged_documents": 0}

    session.execute(delete(ExDocument).where(ExDocument.id.in_(doc_ids)))
    session.commit()
    return {"purged_documents": len(doc_ids)}
