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

DECISIONS = {"accepted", "edited", "rejected", "false_positive", "needs_clarification"}


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

    def audit(self, workspace_id, *, actor, action, object_type=None, object_id=None, detail=None):
        self.s.add(
            AuditLog(
                workspace_id=uuid.UUID(str(workspace_id)),
                actor_user_id=uuid.UUID(str(actor)) if actor else None,
                action=action,
                object_type=object_type,
                object_id=uuid.UUID(str(object_id)) if object_id else None,
                detail=detail or {},
            )
        )
        self.s.commit()

    def queue(self, workspace_id, opportunity_id) -> list:
        return self._store().list(workspace_id, opportunity_id)

    def review_finding(
        self,
        workspace_id,
        finding_id,
        *,
        decision,
        note=None,
        review_reason=None,
        reviewer_id=None,
        opportunity_id=None,
    ) -> object:
        if decision not in DECISIONS:
            raise ReviewError("bad_decision")
        row = self._store().set_review(
            workspace_id,
            finding_id,
            status=decision,
            note=note,
            review_reason=review_reason,
            reviewer_id=reviewer_id,
            opportunity_id=opportunity_id,
        )
        if row is None:
            raise ReviewError("not_found")
        detail = {}
        if note:
            detail["note"] = note
        if review_reason:
            detail["review_reason"] = review_reason
        self.audit(
            workspace_id,
            actor=reviewer_id,
            action=f"finding.{decision}",
            object_type="finding",
            object_id=finding_id,
            detail=detail,
        )
        return row

    def gate(self, workspace_id, opportunity_id) -> dict:
        """Export is allowed only when there are findings and none remain
        `proposed` or `needs_clarification` (Doc §11.4 — export blocked until
        review completes, including clarifications)."""
        rows = self._store().list(workspace_id, opportunity_id)
        by_status: dict[str, int] = {}
        for r in rows:
            by_status[r.review_status] = by_status.get(r.review_status, 0) + 1
        pending = by_status.get("proposed", 0) + by_status.get("needs_clarification", 0)
        return {
            "export_allowed": len(rows) > 0 and pending == 0,
            "total": len(rows),
            "pending": pending,
            "by_status": by_status,
        }

    def audit_trail(self, workspace_id, opportunity_id=None) -> list[AuditLog]:
        opp = uuid.UUID(str(opportunity_id)) if opportunity_id else None
        stmt = select(AuditLog).where(AuditLog.workspace_id == uuid.UUID(str(workspace_id)))
        if opp is not None:
            # Audit logs for an opportunity are those whose finding object is in
            # the opportunity. We load the finding IDs via the findings store.
            rows = self._store().list(workspace_id, opportunity_id)
            finding_ids = {r.id for r in rows}
            stmt = stmt.where(
                AuditLog.object_type == "finding",
                AuditLog.object_id.in_(finding_ids),
            )
        return list(self.s.scalars(stmt.order_by(AuditLog.id.desc())))

    def last_reviewer(self, workspace_id, opportunity_id) -> dict | None:
        """Return the most recent reviewer user id and timestamp for an opportunity."""
        store = self._store()
        rows = store.list(workspace_id, opportunity_id)
        if not rows:
            return None
        finding_ids = {r.id for r in rows}
        log = self.s.scalar(
            select(AuditLog)
            .where(
                AuditLog.workspace_id == uuid.UUID(str(workspace_id)),
                AuditLog.object_type == "finding",
                AuditLog.object_id.in_(finding_ids),
            )
            .order_by(AuditLog.at.desc())
        )
        if log is None:
            return None
        return {
            "reviewer_id": str(log.actor_user_id) if log.actor_user_id else None,
            "reviewed_at": log.at,
        }
