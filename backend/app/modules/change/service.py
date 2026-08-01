"""ChangeService — variation event lifecycle (TS-244 scaffold)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.change.models import (
    ChangeConfirmation,
    ChangeEvent,
    ChangeSource,
)

_EVENT_STATUSES = frozenset({"candidate", "triaged", "confirmed", "rejected", "closed"})
_CONFIRMATION_OUTCOMES = frozenset(
    {
        "changed",
        "not_changed",
        "clarification_only",
        "contractor_risk",
        "client_risk",
        "unknown",
    }
)
_CONFIDENCE_BANDS = frozenset({"high", "medium", "low"})


class ChangeError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class ChangeService:
    def __init__(
        self,
        session: Session,
        *,
        baseline_factory: Callable[[Session], object] | None = None,
        ingestion_factory: Callable[[Session], object] | None = None,
        review_factory: Callable[[Session], object] | None = None,
        publish: Callable[[str, dict], int] | None = None,
    ):
        self.s = session
        self._baseline_factory = baseline_factory
        self._ingestion_factory = ingestion_factory
        self._review_factory = review_factory
        self._publish = publish

    def _baseline(self):
        if self._baseline_factory is None:
            raise ChangeError("baseline_unavailable")
        return self._baseline_factory(self.s)

    def _require_baseline(self, workspace_id, opportunity_id):
        baseline = self._baseline()
        if not hasattr(baseline, "latest"):
            raise ChangeError("baseline_unavailable")
        row = baseline.latest(workspace_id, opportunity_id)
        if row is None:
            raise ChangeError("no_baseline")
        return row

    def list_events(self, workspace_id, opportunity_id) -> list[dict]:
        wid = uuid.UUID(str(workspace_id))
        oid = uuid.UUID(str(opportunity_id))
        rows = list(
            self.s.scalars(
                select(ChangeEvent)
                .where(
                    ChangeEvent.workspace_id == wid,
                    ChangeEvent.opportunity_id == oid,
                )
                .order_by(ChangeEvent.created_at.desc())
            )
        )
        return [self._event_dict(row) for row in rows]

    def get_event(self, workspace_id, event_id) -> dict:
        row = self._get_event_row(workspace_id, event_id)
        return self._event_dict(row, include_sources=True, include_confirmation=True)

    def create_manual_event(
        self,
        workspace_id,
        opportunity_id,
        *,
        title: str,
        reason: str = "other",
        affected_scope: str | None = None,
        confidence_band: str = "medium",
        notice_type: str | None = None,
        trigger_date: date | None = None,
        created_by=None,
        sources: list[dict],
    ) -> dict:
        if not title.strip():
            raise ChangeError("bad_request")
        if confidence_band not in _CONFIDENCE_BANDS:
            raise ChangeError("bad_request")
        if not sources:
            raise ChangeError("source_required")
        baseline = self._require_baseline(workspace_id, opportunity_id)
        wid = uuid.UUID(str(workspace_id))
        oid = uuid.UUID(str(opportunity_id))
        event = ChangeEvent(
            workspace_id=wid,
            opportunity_id=oid,
            baseline_id=baseline.id,
            status="candidate",
            title=title.strip(),
            reason=reason or "other",
            affected_scope=affected_scope,
            confidence_band=confidence_band,
            notice_type=notice_type,
            trigger_date=trigger_date,
            created_by=uuid.UUID(str(created_by)) if created_by else None,
        )
        self.s.add(event)
        self.s.flush()
        for entry in sources:
            quote = (entry.get("source_quote") or "").strip()
            if not quote and not entry.get("document_id"):
                raise ChangeError("source_required")
            if quote and len(quote) > 200:
                raise ChangeError("quote_too_long")
            self.s.add(
                ChangeSource(
                    workspace_id=wid,
                    opportunity_id=oid,
                    change_event_id=event.id,
                    source_kind=entry.get("source_kind", "manual"),
                    document_id=(
                        uuid.UUID(str(entry["document_id"]))
                        if entry.get("document_id")
                        else None
                    ),
                    source_page=entry.get("source_page"),
                    source_quote=quote or None,
                    external_ref=entry.get("external_ref"),
                    text_preview=entry.get("text_preview"),
                    sha256=entry.get("sha256"),
                )
            )
        self.s.commit()
        self.s.refresh(event)
        if self._publish:
            self._publish(
                "change.event_created",
                {
                    "workspace_id": str(wid),
                    "opportunity_id": str(oid),
                    "event_id": str(event.id),
                    "status": event.status,
                    "source_kind": "manual",
                },
            )
        return self._event_dict(event, include_sources=True)

    def record_confirmation(
        self,
        workspace_id,
        event_id,
        *,
        outcome: str,
        confirmed_by,
        note: str | None = None,
        evidence_ids: list | None = None,
    ) -> dict:
        if outcome not in _CONFIRMATION_OUTCOMES:
            raise ChangeError("bad_outcome")
        event = self._get_event_row(workspace_id, event_id)
        row = ChangeConfirmation(
            workspace_id=event.workspace_id,
            opportunity_id=event.opportunity_id,
            change_event_id=event.id,
            outcome=outcome,
            confirmed_by=uuid.UUID(str(confirmed_by)),
            note=note,
            evidence_ids=evidence_ids or [],
        )
        self.s.add(row)
        if outcome == "changed":
            event.status = "confirmed"
        elif outcome in {"not_changed", "contractor_risk"}:
            event.status = "closed"
        self.s.commit()
        self.s.refresh(row)
        if self._review_factory is not None:
            self._review_factory(self.s).audit(
                workspace_id,
                actor=confirmed_by,
                action="change.confirmed",
                object_type="change_event",
                object_id=event.id,
                detail={"outcome": outcome},
            )
        if self._publish:
            self._publish(
                "change.event_confirmed",
                {
                    "workspace_id": str(event.workspace_id),
                    "event_id": str(event.id),
                    "outcome": outcome,
                    "confirmed_by": str(confirmed_by),
                },
            )
        return self._confirmation_dict(row)

    def _get_event_row(self, workspace_id, event_id) -> ChangeEvent:
        row = self.s.scalar(
            select(ChangeEvent).where(
                ChangeEvent.id == uuid.UUID(str(event_id)),
                ChangeEvent.workspace_id == uuid.UUID(str(workspace_id)),
            )
        )
        if row is None:
            raise ChangeError("not_found")
        return row

    def _sources_for(self, event_id) -> list[ChangeSource]:
        return list(
            self.s.scalars(
                select(ChangeSource)
                .where(ChangeSource.change_event_id == event_id)
                .order_by(ChangeSource.created_at)
            )
        )

    def _latest_confirmation(self, event_id) -> ChangeConfirmation | None:
        return self.s.scalar(
            select(ChangeConfirmation)
            .where(ChangeConfirmation.change_event_id == event_id)
            .order_by(ChangeConfirmation.confirmed_at.desc())
        )

    def _source_dict(self, row: ChangeSource) -> dict:
        return {
            "id": str(row.id),
            "source_kind": row.source_kind,
            "document_id": str(row.document_id) if row.document_id else None,
            "source_page": row.source_page,
            "source_quote": row.source_quote,
            "external_ref": row.external_ref,
            "text_preview": row.text_preview,
            "received_at": row.received_at.isoformat() if row.received_at else None,
        }

    def _confirmation_dict(self, row: ChangeConfirmation) -> dict:
        return {
            "id": str(row.id),
            "outcome": row.outcome,
            "confirmed_by": str(row.confirmed_by),
            "confirmed_at": row.confirmed_at.isoformat() if row.confirmed_at else None,
            "note": row.note,
            "evidence_ids": row.evidence_ids or [],
        }

    def _event_dict(
        self,
        row: ChangeEvent,
        *,
        include_sources: bool = False,
        include_confirmation: bool = False,
    ) -> dict:
        payload = {
            "id": str(row.id),
            "opportunity_id": str(row.opportunity_id),
            "baseline_id": str(row.baseline_id) if row.baseline_id else None,
            "status": row.status,
            "title": row.title,
            "reason": row.reason,
            "affected_scope": row.affected_scope,
            "confidence_band": row.confidence_band,
            "notice_type": row.notice_type,
            "trigger_date": row.trigger_date.isoformat() if row.trigger_date else None,
            "notice_deadline": row.notice_deadline.isoformat() if row.notice_deadline else None,
            "notice_deadline_detail": row.notice_deadline_detail or {},
            "impact_links": row.impact_links or {},
            "created_by": str(row.created_by) if row.created_by else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
        if include_sources:
            payload["sources"] = [self._source_dict(s) for s in self._sources_for(row.id)]
        if include_confirmation:
            latest = self._latest_confirmation(row.id)
            payload["latest_confirmation"] = (
                self._confirmation_dict(latest) if latest else None
            )
        return payload
