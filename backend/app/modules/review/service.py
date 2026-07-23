"""ReviewService — the professional-liability spine (Doc §11.4). Humans
accept/edit/reject every finding; each decision is written to the append-only
audit log; export is gated until review is complete.

Consumes the findings store via the injected capability — it never imports the
findings module."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.review.models import AuditLog

DECISIONS = {"accepted", "edited", "rejected"}


class ReviewError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class ReviewService:
    def __init__(self, session: Session, *, store_factory=None):
        self.s = session
        self._store_factory = store_factory

    def _store(self):
        if self._store_factory is None:
            raise ReviewError("findings_unavailable")
        return self._store_factory(self.s)

    def audit(self, org_id, *, actor, action, object_type=None, object_id=None, detail=None):
        self.s.add(
            AuditLog(
                org_id=uuid.UUID(str(org_id)),
                actor_user_id=uuid.UUID(str(actor)) if actor else None,
                action=action,
                object_type=object_type,
                object_id=uuid.UUID(str(object_id)) if object_id else None,
                detail=detail or {},
            )
        )
        self.s.commit()

    def queue(self, org_id, opportunity_id) -> list:
        return self._store().list(org_id, opportunity_id)

    def review_finding(self, org_id, finding_id, *, decision, note, reviewer_id) -> object:
        if decision not in DECISIONS:
            raise ReviewError("bad_decision")
        row = self._store().set_review(
            org_id, finding_id, status=decision, note=note, reviewer_id=reviewer_id
        )
        if row is None:
            raise ReviewError("not_found")
        self.audit(
            org_id,
            actor=reviewer_id,
            action=f"finding.{decision}",
            object_type="finding",
            object_id=finding_id,
            detail={"note": note} if note else {},
        )
        return row

    def gate(self, org_id, opportunity_id) -> dict:
        """Export is allowed only when there are findings and none remain
        `proposed` (Doc §11.4 — export blocked until review completes)."""
        rows = self._store().list(org_id, opportunity_id)
        by_status: dict[str, int] = {}
        for r in rows:
            by_status[r.review_status] = by_status.get(r.review_status, 0) + 1
        pending = by_status.get("proposed", 0)
        return {
            "export_allowed": len(rows) > 0 and pending == 0,
            "total": len(rows),
            "pending": pending,
            "by_status": by_status,
        }

    def audit_trail(self, org_id, opportunity_id=None) -> list[AuditLog]:
        stmt = select(AuditLog).where(AuditLog.org_id == uuid.UUID(str(org_id)))
        return list(self.s.scalars(stmt.order_by(AuditLog.id.desc())))
