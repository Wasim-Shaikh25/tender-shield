"""ChangeService — variation event lifecycle (TS-244+)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.change.baseline_diff import (
    candidates_from_diff,
    clauses_from_segments,
    content_hash,
    normalize_clause,
)
from app.modules.change.impacts import (
    compute_impact_exposure,
    normalize_impact_links,
    validate_impact_links,
)
from app.modules.change.inbox import INBOX_STATUSES, sort_inbox
from app.modules.change.models import (
    ChangeConfirmation,
    ChangeEvent,
    ChangeSource,
)
from app.modules.change.signals import classify_signal

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
_TRIAGE_DECISIONS = frozenset({"triaged", "rejected"})


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
        segment_clauses_fn: Callable[[str], list] | None = None,
        diff_clauses_fn: Callable[..., dict] | None = None,
        findings_factory: Callable[[Session], object] | None = None,
        cost_codes_fn: Callable[..., dict] | None = None,
        publish: Callable[[str, dict], int] | None = None,
    ):
        self.s = session
        self._baseline_factory = baseline_factory
        self._ingestion_factory = ingestion_factory
        self._review_factory = review_factory
        self._segment_clauses_fn = segment_clauses_fn
        self._diff_clauses_fn = diff_clauses_fn
        self._findings_factory = findings_factory
        self._cost_codes_fn = cost_codes_fn
        self._publish = publish

    def _baseline(self):
        if self._baseline_factory is None:
            raise ChangeError("baseline_unavailable")
        return self._baseline_factory(self.s)

    def _ingestion(self):
        if self._ingestion_factory is None:
            raise ChangeError("ingestion_unavailable")
        return self._ingestion_factory(self.s)

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

    def list_inbox(self, workspace_id, opportunity_id) -> dict:
        events = [
            self._event_dict(row, include_sources=True)
            for row in self._inbox_rows(workspace_id, opportunity_id)
        ]
        return {"events": sort_inbox(events)}

    def triage_event(
        self,
        workspace_id,
        event_id,
        *,
        decision: str,
        actor_user_id=None,
    ) -> dict:
        if decision not in _TRIAGE_DECISIONS:
            raise ChangeError("bad_triage_decision")
        event = self._get_event_row(workspace_id, event_id)
        prior = event.status
        if prior == "candidate" and decision not in {"triaged", "rejected"}:
            raise ChangeError("bad_triage_transition")
        if prior == "triaged" and decision != "rejected":
            raise ChangeError("bad_triage_transition")
        if prior not in INBOX_STATUSES:
            raise ChangeError("bad_triage_transition")
        event.status = decision
        self.s.commit()
        self.s.refresh(event)
        if self._review_factory is not None:
            self._review_factory(self.s).audit(
                workspace_id,
                actor=actor_user_id,
                action="change.triaged",
                object_type="change_event",
                object_id=event.id,
                detail={"decision": decision, "prior_status": prior},
            )
        if self._publish:
            self._publish(
                "change.event_triaged",
                {
                    "workspace_id": str(event.workspace_id),
                    "event_id": str(event.id),
                    "prior_status": prior,
                    "new_status": decision,
                },
            )
        return self._event_dict(event, include_sources=True)

    def update_impacts(
        self,
        workspace_id,
        event_id,
        *,
        impact_links: dict,
    ) -> dict:
        event = self._get_event_row(workspace_id, event_id)
        links = normalize_impact_links(impact_links)
        valid_cost_codes, valid_findings = self._impact_id_sets(
            workspace_id, event.opportunity_id
        )
        try:
            validate_impact_links(
                links,
                valid_cost_code_ids=valid_cost_codes,
                valid_finding_ids=valid_findings,
            )
        except ValueError as exc:
            code = str(exc)
            if code == "invalid_cost_code":
                raise ChangeError("invalid_cost_code") from exc
            raise ChangeError("invalid_finding") from exc

        findings_by_id = self._findings_by_id(workspace_id, event.opportunity_id)
        summary = compute_impact_exposure(links, findings_by_id)
        event.impact_links = {**links, "exposure_summary": summary}
        self.s.commit()
        self.s.refresh(event)
        return self._event_dict(event, include_sources=True)

    def list_confirmations(self, workspace_id, event_id) -> list[dict]:
        event = self._get_event_row(workspace_id, event_id)
        rows = list(
            self.s.scalars(
                select(ChangeConfirmation)
                .where(ChangeConfirmation.change_event_id == event.id)
                .order_by(ChangeConfirmation.confirmed_at.desc())
            )
        )
        return [self._confirmation_dict(row) for row in rows]

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
        event = self._create_event_with_sources(
            workspace_id,
            opportunity_id,
            baseline_id=baseline.id,
            title=title.strip(),
            reason=reason or "other",
            affected_scope=affected_scope,
            confidence_band=confidence_band,
            notice_type=notice_type,
            trigger_date=trigger_date,
            created_by=created_by,
            sources=sources,
            publish_kind="manual",
        )
        return self._event_dict(event, include_sources=True)

    def run_baseline_diff(
        self,
        workspace_id,
        opportunity_id,
        *,
        document_id: str | None = None,
        text: str | None = None,
        created_by=None,
    ) -> dict:
        if self._segment_clauses_fn is None or self._diff_clauses_fn is None:
            raise ChangeError("diff_unavailable")
        baseline = self._require_baseline(workspace_id, opportunity_id)
        baseline_clauses = [
            normalize_clause(c) for c in (baseline.snapshot or {}).get("clauses", [])
        ]
        doc_id = document_id
        if text is None:
            if not document_id:
                raise ChangeError("bad_request")
            text = self._document_text(workspace_id, document_id)
            if not text.strip():
                raise ChangeError("not_found")
        else:
            text = text.strip()
            if not text:
                raise ChangeError("bad_request")

        new_clauses = clauses_from_segments(self._segment_clauses_fn(text))
        diff = self._diff_clauses_fn(baseline_clauses, new_clauses)
        reason = "spec_revision"
        if doc_id:
            doc = self._ingestion().get_document(workspace_id, doc_id)
            if doc is not None and getattr(doc, "kind", None) in {"drawing_log", "instruction"}:
                reason = "drawing_revision" if doc.kind == "drawing_log" else "instruction"

        created_events: list[dict] = []
        new_count = 0
        attached = 0
        for candidate in candidates_from_diff(diff, document_id=doc_id, reason=reason):
            event, was_new = self._upsert_candidate(
                workspace_id,
                opportunity_id,
                baseline_id=baseline.id,
                created_by=created_by,
                **candidate,
            )
            created_events.append(self._event_dict(event, include_sources=True))
            if was_new:
                new_count += 1
            else:
                attached += 1

        return {
            "diff": diff,
            "events": created_events,
            "created": new_count,
            "attached_to_existing": attached,
        }

    def ingest_signal(
        self,
        workspace_id,
        opportunity_id,
        *,
        signal_kind: str,
        text: str,
        title: str | None = None,
        external_ref: str | None = None,
        created_by=None,
    ) -> dict:
        baseline = self._require_baseline(workspace_id, opportunity_id)
        try:
            classified = classify_signal(signal_kind, text, title=title)
        except ValueError as exc:
            code = str(exc)
            if code == "bad_signal_kind":
                raise ChangeError("bad_signal_kind") from exc
            raise ChangeError("bad_request") from exc

        sha = content_hash(signal_kind, classified["source_quote"], external_ref or "")
        event, was_new = self._upsert_candidate(
            workspace_id,
            opportunity_id,
            baseline_id=baseline.id,
            created_by=created_by,
            title=classified["title"],
            reason=classified["reason"],
            confidence_band=classified["confidence_band"],
            notice_type=classified["notice_type"],
            source_kind=classified["source_kind"],
            source_quote=classified["source_quote"],
            text_preview=classified["text_preview"],
            external_ref=external_ref,
            sha256=sha,
        )
        return {
            "event": self._event_dict(event, include_sources=True),
            "created": was_new,
            "classification": classified,
        }

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
        if event.status not in {"candidate", "triaged", "confirmed"}:
            raise ChangeError("bad_confirmation_state")
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
        elif outcome in {"not_changed", "contractor_risk", "client_risk"}:
            event.status = "closed"
        elif outcome in {"clarification_only", "unknown"}:
            event.status = "triaged"
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

    def _inbox_rows(self, workspace_id, opportunity_id) -> list[ChangeEvent]:
        wid = uuid.UUID(str(workspace_id))
        oid = uuid.UUID(str(opportunity_id))
        return list(
            self.s.scalars(
                select(ChangeEvent).where(
                    ChangeEvent.workspace_id == wid,
                    ChangeEvent.opportunity_id == oid,
                    ChangeEvent.status.in_(INBOX_STATUSES),
                )
            )
        )

    def _impact_id_sets(self, workspace_id, opportunity_id) -> tuple[set[str], set[str]]:
        cost_codes: set[str] = set()
        if self._cost_codes_fn is not None:
            payload = self._cost_codes_fn(self.s, workspace_id, opportunity_id)
            cost_codes = {c["id"] for c in payload.get("codes", [])}
        findings = self._findings_by_id(workspace_id, opportunity_id)
        return cost_codes, set(findings.keys())

    def _findings_by_id(self, workspace_id, opportunity_id) -> dict[str, object]:
        if self._findings_factory is None:
            return {}
        store = self._findings_factory(self.s)
        if not hasattr(store, "list"):
            return {}
        rows = store.list(workspace_id, opportunity_id)
        return {str(row.id): row for row in rows}

    def _document_text(self, workspace_id, document_id: str) -> str:
        ing = self._ingestion()
        doc = ing.get_document(workspace_id, document_id)
        if doc is None:
            raise ChangeError("not_found")
        payload = ing.get_doc_text(workspace_id, document_id)
        pages = payload.get("pages") or {}
        if not pages:
            return ""
        return "\n".join(f"[p{page}]\n{text}" for page, text in sorted(pages.items()))

    def _upsert_candidate(
        self,
        workspace_id,
        opportunity_id,
        *,
        baseline_id,
        created_by,
        title: str,
        reason: str,
        confidence_band: str = "medium",
        notice_type: str | None = None,
        source_kind: str,
        source_quote: str,
        document_id: str | None = None,
        source_page: int | None = None,
        text_preview: str | None = None,
        external_ref: str | None = None,
        sha256: str | None = None,
        affected_scope: str | None = None,
        trigger_date: date | None = None,
    ) -> tuple[ChangeEvent, bool]:
        wid = uuid.UUID(str(workspace_id))
        oid = uuid.UUID(str(opportunity_id))
        digest = sha256 or content_hash(source_kind, source_quote, str(document_id or ""))
        existing = self._find_recent_duplicate(wid, oid, digest, source_kind)
        source_entry = {
            "source_kind": source_kind,
            "document_id": document_id,
            "source_page": source_page,
            "source_quote": source_quote,
            "external_ref": external_ref,
            "text_preview": text_preview,
            "sha256": digest,
        }
        if existing is not None:
            self._add_source(wid, oid, existing.id, source_entry)
            self.s.commit()
            self.s.refresh(existing)
            return existing, False

        event = self._create_event_with_sources(
            workspace_id,
            opportunity_id,
            baseline_id=baseline_id,
            title=title,
            reason=reason,
            affected_scope=affected_scope,
            confidence_band=confidence_band,
            notice_type=notice_type,
            trigger_date=trigger_date,
            created_by=created_by,
            sources=[source_entry],
            publish_kind=source_kind,
        )
        return event, True

    def _find_recent_duplicate(
        self, workspace_id: uuid.UUID, opportunity_id: uuid.UUID, sha256: str, source_kind: str
    ) -> ChangeEvent | None:
        since = datetime.now(UTC) - timedelta(hours=24)
        rows = self.s.scalars(
            select(ChangeSource)
            .where(
                ChangeSource.workspace_id == workspace_id,
                ChangeSource.opportunity_id == opportunity_id,
                ChangeSource.source_kind == source_kind,
                ChangeSource.sha256 == sha256,
                ChangeSource.created_at >= since,
            )
            .order_by(ChangeSource.created_at.desc())
        ).all()
        if not rows:
            return None
        return self.s.get(ChangeEvent, rows[0].change_event_id)

    def _create_event_with_sources(
        self,
        workspace_id,
        opportunity_id,
        *,
        baseline_id,
        title: str,
        reason: str,
        affected_scope: str | None,
        confidence_band: str,
        notice_type: str | None,
        trigger_date: date | None,
        created_by,
        sources: list[dict],
        publish_kind: str,
    ) -> ChangeEvent:
        wid = uuid.UUID(str(workspace_id))
        oid = uuid.UUID(str(opportunity_id))
        event = ChangeEvent(
            workspace_id=wid,
            opportunity_id=oid,
            baseline_id=baseline_id,
            status="candidate",
            title=title,
            reason=reason,
            affected_scope=affected_scope,
            confidence_band=confidence_band,
            notice_type=notice_type,
            trigger_date=trigger_date,
            created_by=uuid.UUID(str(created_by)) if created_by else None,
        )
        self.s.add(event)
        self.s.flush()
        for entry in sources:
            self._add_source(wid, oid, event.id, entry)
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
                    "source_kind": publish_kind,
                },
            )
        return event

    def _add_source(
        self, workspace_id: uuid.UUID, opportunity_id: uuid.UUID, event_id: uuid.UUID, entry: dict
    ) -> None:
        quote = (entry.get("source_quote") or "").strip()
        if not quote and not entry.get("document_id"):
            raise ChangeError("source_required")
        if quote and len(quote) > 200:
            raise ChangeError("quote_too_long")
        self.s.add(
            ChangeSource(
                workspace_id=workspace_id,
                opportunity_id=opportunity_id,
                change_event_id=event_id,
                source_kind=entry.get("source_kind", "manual"),
                document_id=(
                    uuid.UUID(str(entry["document_id"])) if entry.get("document_id") else None
                ),
                source_page=entry.get("source_page"),
                source_quote=quote or None,
                external_ref=entry.get("external_ref"),
                text_preview=entry.get("text_preview"),
                sha256=entry.get("sha256"),
            )
        )

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
