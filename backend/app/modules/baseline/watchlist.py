"""Project watchlist helpers (TS-237)."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.baseline.models import WatchlistControl

_WATCH_SEVERITIES = frozenset({"critical", "high"})
_CADENCE_DAYS = {
    "weekly": 7,
    "fortnightly": 14,
    "monthly": 30,
    "milestone": 90,
}


def obligation_key(finding: dict) -> str:
    pattern_id = finding.get("pattern_id")
    if pattern_id:
        return hashlib.sha256(str(pattern_id).encode()).hexdigest()
    raw = f"{finding.get('category', '')}|{finding.get('title', '')}"
    return hashlib.sha256(raw.encode()).hexdigest()


def seed_watchlist(
    session: Session,
    *,
    workspace_id,
    opportunity_id,
    baseline_id,
    findings: list[dict],
) -> list[WatchlistControl]:
    ws = uuid.UUID(str(workspace_id))
    opp = uuid.UUID(str(opportunity_id))
    base = uuid.UUID(str(baseline_id))
    created: list[WatchlistControl] = []
    for finding in findings:
        if finding.get("severity") not in _WATCH_SEVERITIES:
            continue
        key = obligation_key(finding)
        existing = session.scalar(
            select(WatchlistControl).where(
                WatchlistControl.workspace_id == ws,
                WatchlistControl.opportunity_id == opp,
                WatchlistControl.obligation_key == key,
                WatchlistControl.status == "active",
            )
        )
        if existing is not None:
            continue
        finding_id = finding.get("id")
        row = WatchlistControl(
            workspace_id=ws,
            opportunity_id=opp,
            baseline_id=base,
            finding_id=uuid.UUID(str(finding_id)) if finding_id else None,
            obligation_key=key,
            title=finding.get("title") or "",
            severity=finding.get("severity") or "high",
            review_cadence="monthly",
            status="active",
            source_page=finding.get("source_page"),
            source_quote=finding.get("source_quote"),
            document_id=(
                uuid.UUID(str(finding["document_id"])) if finding.get("document_id") else None
            ),
        )
        session.add(row)
        created.append(row)
    if created:
        session.commit()
        for row in created:
            session.refresh(row)
    return created


def control_dict(row: WatchlistControl) -> dict:
    return {
        "id": str(row.id),
        "opportunity_id": str(row.opportunity_id),
        "baseline_id": str(row.baseline_id),
        "finding_id": str(row.finding_id) if row.finding_id else None,
        "obligation_key": row.obligation_key,
        "title": row.title,
        "severity": row.severity,
        "owner_user_id": str(row.owner_user_id) if row.owner_user_id else None,
        "trigger_text": row.trigger_text,
        "review_cadence": row.review_cadence,
        "next_review_at": row.next_review_at.isoformat() if row.next_review_at else None,
        "status": row.status,
        "source_page": row.source_page,
        "source_quote": row.source_quote,
        "document_id": str(row.document_id) if row.document_id else None,
    }


def apply_cadence(row: WatchlistControl) -> None:
    days = _CADENCE_DAYS.get(row.review_cadence or "monthly", 30)
    row.next_review_at = datetime.now(UTC) + timedelta(days=days)
