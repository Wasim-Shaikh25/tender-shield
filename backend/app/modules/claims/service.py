"""ClaimsService — chronology, quantum, delay register and negotiation lifecycle."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.claims.models import (
    Claim,
    ClaimChronologyEntry,
    ClaimDelayEvent,
    ClaimDraft,
    ClaimEvidenceChecklistItem,
    ClaimNegotiation,
    ClaimQuantumLineItem,
    ClaimResponse,
    ClaimSettlement,
)

_CLAIM_TYPES = frozenset(
    {"variation", "extension_of_time", "disruption", "prolongation", "final_account"}
)

_DRAFT_KINDS = frozenset({"particulars", "variation_proposal", "eot", "full_pack"})

_VALID_PARTIES = frozenset({"contractor", "employer", "engineer", "other"})

_OPPOSING_PARTIES: dict[str, frozenset[str]] = {
    "contractor": frozenset({"employer", "engineer"}),
    "employer": frozenset({"contractor"}),
    "engineer": frozenset({"contractor"}),
}

_CLAIM_TYPE_CHECKLIST = {
    "variation": {
        "instruction",
        "baseline",
        "revised_scope",
        "labour",
        "plant",
        "material",
        "schedule",
        "photos",
        "approvals",
        "quantum",
        "delay",
        "correspondence",
    },
    "extension_of_time": {
        "instruction",
        "baseline",
        "schedule",
        "delay",
        "photos",
        "approvals",
        "correspondence",
        "quantum",
    },
    "disruption": {
        "instruction",
        "baseline",
        "revised_scope",
        "labour",
        "plant",
        "material",
        "schedule",
        "photos",
        "approvals",
        "correspondence",
        "quantum",
    },
    "prolongation": {
        "instruction",
        "baseline",
        "schedule",
        "delay",
        "photos",
        "approvals",
        "correspondence",
        "quantum",
    },
    "final_account": {
        "instruction",
        "baseline",
        "revised_scope",
        "labour",
        "plant",
        "material",
        "schedule",
        "photos",
        "approvals",
        "quantum",
        "delay",
        "correspondence",
    },
}

# Evidence record_type -> checklist item(s) that it satisfies.
_EVIDENCE_ITEM_MAP = {
    "site_instruction": {"instruction"},
    "drawing_revision": {"revised_scope"},
    "photograph": {"photos"},
    "geotagged_photo": {"photos"},
    "labour": {"labour"},
    "plant": {"plant"},
    "material": {"material"},
    "measurement": {"quantum"},
    "daily_report": {"schedule", "correspondence"},
    "meeting_minutes": {"approvals", "correspondence"},
    "correspondence": {"correspondence", "approvals"},
    "daywork": {"quantum"},
}

_ENTRY_TYPE_ORDER = {
    "event": 0,
    "notice": 1,
    "evidence": 2,
    "delay": 3,
    "correspondence": 4,
    "response": 5,
    "negotiation": 6,
    "settlement": 7,
    "submission": 8,
}


class ClaimsError(Exception):
    def __init__(self, code: str, detail: dict | None = None):
        super().__init__(code)
        self.code = code
        self.detail = detail or {}


def _to_uuid(value: Any) -> uuid.UUID:
    return uuid.UUID(str(value))


def _as_utc(dt: datetime | date | None) -> datetime | None:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt
    return datetime.combine(dt, time.min, tzinfo=UTC)


def _avg(values: list[int]) -> int:
    if not values:
        return 0
    return int(sum(values) / len(values))


def _rate(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return 0
    return int(round(100 * numerator / denominator))


class ClaimsService:
    def __init__(
        self,
        session: Session,
        *,
        change_factory: Callable[[Session], Any] | None = None,
        evidence_factory: Callable[[Session], Any] | None = None,
        baseline_factory: Callable[[Session], Any] | None = None,
        approval_matrix_factory: Callable[[Session], Any] | None = None,
        ingestion_factory: Callable[[Session], Any] | None = None,
        drafting_factory: Callable[[Session], Any] | None = None,
        outcomes_factory: Callable[[Session], Any] | None = None,
        analytics_factory: Callable[[Session], Any] | None = None,
        publish: Callable[[str, dict], int] | None = None,
    ):
        self.s = session
        self._change_factory = change_factory
        self._evidence_factory = evidence_factory
        self._baseline_factory = baseline_factory
        self._approval_matrix_factory = approval_matrix_factory
        self._ingestion_factory = ingestion_factory
        self._drafting_factory = drafting_factory
        self._outcomes_factory = outcomes_factory
        self._analytics_factory = analytics_factory
        self._publish = publish

    # ---- lifecycle ---------------------------------------------------------

    def create_claim(
        self,
        workspace_id,
        opportunity_id,
        *,
        claim_type: str,
        title: str,
        description: str | None = None,
        claimant_party: str | None = None,
        change_event_id: str | None = None,
        baseline_id: str | None = None,
        claim_amount_minor: int | None = None,
        currency: str = "INR",
        created_by,
    ) -> dict:
        if claim_type not in _CLAIM_TYPES:
            raise ClaimsError("bad_claim_type")
        if not title.strip():
            raise ClaimsError("bad_request")
        if claimant_party and claimant_party not in _VALID_PARTIES:
            raise ClaimsError("bad_claimant_party")
        wid = _to_uuid(workspace_id)
        oid = _to_uuid(opportunity_id)
        baseline = _to_uuid(baseline_id) if baseline_id else None
        event_id = _to_uuid(change_event_id) if change_event_id else None

        if event_id and self._change_factory is not None:
            change = self._change_factory(self.s)
            if hasattr(change, "get_event"):
                event = change.get_event(wid, event_id)
                if event.get("opportunity_id") != str(oid):
                    raise ClaimsError("event_opportunity_mismatch")
                baseline = baseline or (
                    _to_uuid(event["baseline_id"]) if event.get("baseline_id") else None
                )

        row = Claim(
            workspace_id=wid,
            opportunity_id=oid,
            change_event_id=event_id,
            baseline_id=baseline,
            claim_type=claim_type,
            title=title.strip(),
            description=description,
            claimant_party=claimant_party,
            claim_amount_minor=claim_amount_minor,
            currency=currency,
            created_by=_to_uuid(created_by),
        )
        self.s.add(row)
        self.s.commit()
        self.s.refresh(row)
        _ensure_checklist(self.s, wid, row)
        self.s.commit()
        if self._publish:
            self._publish(
                "claim.created",
                {
                    "workspace_id": str(wid),
                    "opportunity_id": str(oid),
                    "claim_id": str(row.id),
                    "claim_type": claim_type,
                },
            )
        return self._claim_dict(row)

    def list_claims(self, workspace_id, opportunity_id) -> list[dict]:
        wid = _to_uuid(workspace_id)
        oid = _to_uuid(opportunity_id)
        rows = list(
            self.s.scalars(
                select(Claim)
                .where(Claim.workspace_id == wid, Claim.opportunity_id == oid)
                .order_by(Claim.created_at.desc())
            )
        )
        return [self._enriched_claim_dict(row) for row in rows]

    def get_claim(self, workspace_id, claim_id) -> dict:
        row = self._get_claim_row(workspace_id, claim_id)
        return self._enriched_claim_dict(row)

    def update_claim(
        self,
        workspace_id,
        claim_id,
        *,
        title: str | None = None,
        description: str | None = None,
        claimant_party: str | None = None,
        claim_type: str | None = None,
        claim_amount_minor: int | None = None,
        currency: str | None = None,
    ) -> dict:
        row = self._get_claim_row(workspace_id, claim_id)
        if row.status != "draft":
            raise ClaimsError("not_editable")
        if claim_type is not None and claim_type not in _CLAIM_TYPES:
            raise ClaimsError("bad_claim_type")
        if claimant_party is not None and claimant_party not in _VALID_PARTIES:
            raise ClaimsError("bad_claimant_party")
        if title is not None:
            if not title.strip():
                raise ClaimsError("bad_request")
            row.title = title.strip()
        if description is not None:
            row.description = description
        if claimant_party is not None:
            row.claimant_party = claimant_party
        if claim_type is not None:
            row.claim_type = claim_type
            _ensure_checklist(self.s, row.workspace_id, row)
        if claim_amount_minor is not None:
            row.claim_amount_minor = claim_amount_minor
        if currency is not None:
            row.currency = currency
        self.s.commit()
        self.s.refresh(row)
        return self._enriched_claim_dict(row)

    def submit_claim(self, workspace_id, claim_id, submitted_by) -> dict:
        row = self._get_claim_row(workspace_id, claim_id)
        if row.status != "draft":
            raise ClaimsError("bad_status_transition")
        integrity = self.chain_integrity(workspace_id, claim_id)
        if integrity["status"] != "intact":
            raise ClaimsError("chain_broken", integrity)
        wid = row.workspace_id
        amount = row.claim_amount_minor or 0
        if self._approval_matrix_factory is not None:
            matrix = self._approval_matrix_factory(self.s)
            if hasattr(matrix, "check"):
                decision = matrix.check(
                    wid,
                    role="estimator",
                    action="claim_submit",
                    amount_minor=amount,
                )
                if not getattr(decision, "allowed", True):
                    raise ClaimsError(
                        "approval_denied",
                        {"reason": getattr(decision, "reason", None)},
                    )
        row.status = "submitted"
        row.submitted_at = datetime.now(UTC)
        row.submitted_by = _to_uuid(submitted_by)
        self.s.add(
            ClaimChronologyEntry(
                workspace_id=wid,
                opportunity_id=row.opportunity_id,
                claim_id=row.id,
                entry_type="submission",
                source_kind="claim",
                source_id=row.id,
                title="Claim submitted",
                occurred_at=row.submitted_at,
                created_at=row.submitted_at,
            )
        )
        self.s.commit()
        self.s.refresh(row)
        if self._publish:
            self._publish(
                "claim.submitted",
                {
                    "workspace_id": str(wid),
                    "claim_id": str(row.id),
                    "submitted_by": str(submitted_by),
                },
            )
        return self._claim_dict(row)

    # ---- chronology --------------------------------------------------------

    def chronology_for_claim(self, workspace_id, claim_id) -> list[dict]:
        row = self._get_claim_row(workspace_id, claim_id)
        entries: list[dict] = []

        # Change event and sources.
        if row.change_event_id and self._change_factory is not None:
            change = self._change_factory(self.s)
            if hasattr(change, "get_event"):
                try:
                    event = change.get_event(row.workspace_id, row.change_event_id)
                    entries.append(_event_entry(event, row.id, row.opportunity_id))
                    for source in event.get("sources", []):
                        entries.append(_source_entry(source, event, row.id, row.opportunity_id))
                except Exception:
                    pass

        # Evidence records.
        if row.change_event_id and self._evidence_factory is not None:
            evidence = self._evidence_factory(self.s)
            if hasattr(evidence, "list_for_event"):
                try:
                    records = evidence.list_for_event(row.workspace_id, row.change_event_id)
                    for rec in records:
                        entries.append(_evidence_entry(rec, row.id, row.opportunity_id))
                except Exception:
                    pass

        # Claim-owned timeline rows.
        entries.extend(self._chronology_rows(row.id, row.opportunity_id))

        # Sort by occurred_at, then entry type order.
        entries.sort(
            key=lambda e: (
                _as_utc(datetime.fromisoformat(e["occurred_at"]))
                or datetime.min.replace(tzinfo=UTC),
                _ENTRY_TYPE_ORDER.get(e["entry_type"], 99),
            )
        )
        return entries

    # ---- evidence checklist ------------------------------------------------

    def checklist_for_claim(self, workspace_id, claim_id) -> list[dict]:
        row = self._get_claim_row(workspace_id, claim_id)
        _ensure_checklist(self.s, row.workspace_id, row)
        evidence = []
        if row.change_event_id and self._evidence_factory is not None:
            evidence_service = self._evidence_factory(self.s)
            if hasattr(evidence_service, "list_for_event"):
                try:
                    evidence = evidence_service.list_for_event(
                        row.workspace_id, row.change_event_id
                    )
                except Exception:
                    evidence = []
        line_items = list(
            self.s.scalars(
                select(ClaimQuantumLineItem).where(
                    ClaimQuantumLineItem.workspace_id == row.workspace_id,
                    ClaimQuantumLineItem.claim_id == row.id,
                )
            )
        )
        delay_events = list(
            self.s.scalars(
                select(ClaimDelayEvent).where(
                    ClaimDelayEvent.workspace_id == row.workspace_id,
                    ClaimDelayEvent.claim_id == row.id,
                )
            )
        )
        _refresh_checklist(
            self.s,
            row,
            evidence_records=evidence,
            line_items=line_items,
            delay_events=delay_events,
        )
        items = list(
            self.s.scalars(
                select(ClaimEvidenceChecklistItem)
                .where(
                    ClaimEvidenceChecklistItem.workspace_id == row.workspace_id,
                    ClaimEvidenceChecklistItem.claim_id == row.id,
                )
                .order_by(ClaimEvidenceChecklistItem.item_type)
            )
        )
        return [self._checklist_item_dict(item) for item in items]

    def override_checklist_item(
        self, workspace_id, claim_id, item_id, *, override_note: str
    ) -> dict:
        row = self._get_claim_row(workspace_id, claim_id)
        item = self.s.scalar(
            select(ClaimEvidenceChecklistItem).where(
                ClaimEvidenceChecklistItem.id == _to_uuid(item_id),
                ClaimEvidenceChecklistItem.workspace_id == row.workspace_id,
                ClaimEvidenceChecklistItem.claim_id == row.id,
            )
        )
        if item is None:
            raise ClaimsError("not_found")
        item.present = True
        item.override_note = override_note.strip() or None
        self.s.commit()
        self.s.refresh(item)
        return self._checklist_item_dict(item)

    # ---- quantum workspace -------------------------------------------------

    def quantum_for_claim(self, workspace_id, claim_id) -> dict:
        row = self._get_claim_row(workspace_id, claim_id)
        items = list(
            self.s.scalars(
                select(ClaimQuantumLineItem)
                .where(
                    ClaimQuantumLineItem.workspace_id == row.workspace_id,
                    ClaimQuantumLineItem.claim_id == row.id,
                )
                .order_by(ClaimQuantumLineItem.created_at.asc())
            )
        )
        measured_total = 0
        daywork_total = 0
        line_dicts = []
        for item in items:
            d = self._line_item_dict(item)
            line_dicts.append(d)
            measured_total += d["measured_total_minor"]
            daywork_total += d["daywork_total_minor"]
        total = measured_total + daywork_total
        return {
            "currency": row.currency,
            "measured_total_minor": measured_total,
            "daywork_total_minor": daywork_total,
            "total_minor": total,
            "line_items": line_dicts,
        }

    def add_line_item(
        self,
        workspace_id,
        claim_id,
        *,
        description: str,
        quantity: Decimal,
        unit: str,
        rate_minor: int,
        daywork_days: int | None = None,
        daywork_rate_minor: int | None = None,
        cost_code_id: str | None = None,
        currency: str | None = None,
        created_by,
    ) -> dict:
        row = self._get_claim_row(workspace_id, claim_id)
        if not description.strip():
            raise ClaimsError("bad_request")
        if quantity <= 0:
            raise ClaimsError("bad_quantity")
        if rate_minor < 0:
            raise ClaimsError("bad_rate")
        item = ClaimQuantumLineItem(
            workspace_id=row.workspace_id,
            claim_id=row.id,
            cost_code_id=_to_uuid(cost_code_id) if cost_code_id else None,
            description=description.strip(),
            quantity=quantity,
            unit=unit.strip(),
            rate_minor=rate_minor,
            daywork_days=daywork_days,
            daywork_rate_minor=daywork_rate_minor,
            currency=(currency or row.currency),
            created_by=_to_uuid(created_by),
        )
        self.s.add(item)
        self.s.commit()
        self.s.refresh(item)
        if self._publish:
            self._publish(
                "quantum.computed",
                {
                    "workspace_id": str(row.workspace_id),
                    "claim_id": str(row.id),
                    "total_minor": self.quantum_for_claim(row.workspace_id, row.id)[
                        "total_minor"
                    ],
                    "currency": item.currency,
                },
            )
        return self._line_item_dict(item)

    def update_line_item(
        self,
        workspace_id,
        claim_id,
        line_id,
        *,
        description: str | None = None,
        quantity: Decimal | None = None,
        unit: str | None = None,
        rate_minor: int | None = None,
        daywork_days: int | None = None,
        daywork_rate_minor: int | None = None,
    ) -> dict:
        row = self._get_claim_row(workspace_id, claim_id)
        item = self.s.scalar(
            select(ClaimQuantumLineItem).where(
                ClaimQuantumLineItem.id == _to_uuid(line_id),
                ClaimQuantumLineItem.workspace_id == row.workspace_id,
                ClaimQuantumLineItem.claim_id == row.id,
            )
        )
        if item is None:
            raise ClaimsError("not_found")
        if description is not None:
            item.description = description.strip()
        if quantity is not None:
            if quantity <= 0:
                raise ClaimsError("bad_quantity")
            item.quantity = quantity
        if unit is not None:
            item.unit = unit.strip()
        if rate_minor is not None:
            if rate_minor < 0:
                raise ClaimsError("bad_rate")
            item.rate_minor = rate_minor
        if daywork_days is not None:
            item.daywork_days = daywork_days
        if daywork_rate_minor is not None:
            item.daywork_rate_minor = daywork_rate_minor
        self.s.commit()
        self.s.refresh(item)
        return self._line_item_dict(item)

    def delete_line_item(self, workspace_id, claim_id, line_id) -> None:
        row = self._get_claim_row(workspace_id, claim_id)
        item = self.s.scalar(
            select(ClaimQuantumLineItem).where(
                ClaimQuantumLineItem.id == _to_uuid(line_id),
                ClaimQuantumLineItem.workspace_id == row.workspace_id,
                ClaimQuantumLineItem.claim_id == row.id,
            )
        )
        if item is None:
            raise ClaimsError("not_found")
        self.s.delete(item)
        self.s.commit()

    # ---- delay register ----------------------------------------------------

    def list_delay_events(self, workspace_id, opportunity_id) -> list[dict]:
        wid = _to_uuid(workspace_id)
        oid = _to_uuid(opportunity_id)
        rows = list(
            self.s.scalars(
                select(ClaimDelayEvent)
                .where(
                    ClaimDelayEvent.workspace_id == wid,
                    ClaimDelayEvent.opportunity_id == oid,
                )
                .order_by(ClaimDelayEvent.event_date.asc())
            )
        )
        return [self._delay_event_dict(row) for row in rows]

    def add_delay_event(
        self,
        workspace_id,
        opportunity_id,
        *,
        event_date: date,
        description: str,
        delay_days: int,
        programme_activity: str | None = None,
        source_page: int | None = None,
        source_quote: str | None = None,
        document_id: str | None = None,
        claim_id: str | None = None,
        change_event_id: str | None = None,
        created_by,
    ) -> dict:
        if delay_days < 0:
            raise ClaimsError("bad_delay_days")
        if not description.strip():
            raise ClaimsError("bad_request")
        wid = _to_uuid(workspace_id)
        oid = _to_uuid(opportunity_id)
        claim = None
        if claim_id:
            claim = self._get_claim_row(workspace_id, claim_id)
            if claim.opportunity_id != oid:
                raise ClaimsError("claim_opportunity_mismatch")
        row = ClaimDelayEvent(
            workspace_id=wid,
            opportunity_id=oid,
            claim_id=claim.id if claim else None,
            change_event_id=_to_uuid(change_event_id) if change_event_id else None,
            event_date=event_date,
            description=description.strip(),
            delay_days=delay_days,
            programme_activity=programme_activity,
            source_page=source_page,
            source_quote=source_quote[:200] if source_quote else None,
            document_id=_to_uuid(document_id) if document_id else None,
            created_by=_to_uuid(created_by),
        )
        self.s.add(row)
        self.s.commit()
        self.s.refresh(row)
        if self._publish:
            self._publish(
                "delay.registered",
                {
                    "workspace_id": str(wid),
                    "opportunity_id": str(oid),
                    "delay_event_id": str(row.id),
                },
            )
        return self._delay_event_dict(row)

    # ---- response / negotiation / settlement -------------------------------

    def record_response(
        self,
        workspace_id,
        claim_id,
        *,
        response_kind: str,
        received_at: date,
        responder: str,
        due_at: date | None = None,
        notes: str | None = None,
        document_id: str | None = None,
        created_by,
    ) -> dict:
        row = self._get_claim_row(workspace_id, claim_id)
        if response_kind not in {"acknowledgment", "rejection", "request_info", "counter_proposal"}:
            raise ClaimsError("bad_response_kind")
        response = ClaimResponse(
            workspace_id=row.workspace_id,
            claim_id=row.id,
            response_kind=response_kind,
            received_at=received_at,
            due_at=due_at,
            responder=responder.strip(),
            notes=notes,
            document_id=_to_uuid(document_id) if document_id else None,
            created_by=_to_uuid(created_by),
        )
        self.s.add(response)
        if row.status == "submitted":
            row.status = "under_review"
        self.s.commit()
        self.s.refresh(response)
        if self._publish:
            self._publish(
                "claim.response_received",
                {
                    "workspace_id": str(row.workspace_id),
                    "claim_id": str(row.id),
                    "response_kind": response_kind,
                    "due_date": due_at.isoformat() if due_at else None,
                },
            )
        return self._response_dict(response)

    def record_negotiation(
        self,
        workspace_id,
        claim_id,
        *,
        offered_amount_minor: int,
        counter_amount_minor: int | None = None,
        status: str = "open",
        recorded_by,
    ) -> dict:
        row = self._get_claim_row(workspace_id, claim_id)
        if status not in {"open", "accepted", "rejected"}:
            raise ClaimsError("bad_negotiation_status")
        last = self.s.scalar(
            select(ClaimNegotiation)
            .where(
                ClaimNegotiation.workspace_id == row.workspace_id,
                ClaimNegotiation.claim_id == row.id,
            )
            .order_by(ClaimNegotiation.round.desc())
        )
        next_round = (last.round + 1) if last else 1
        neg = ClaimNegotiation(
            workspace_id=row.workspace_id,
            claim_id=row.id,
            round=next_round,
            offered_amount_minor=offered_amount_minor,
            counter_amount_minor=counter_amount_minor,
            status=status,
            recorded_by=_to_uuid(recorded_by),
        )
        self.s.add(neg)
        if row.status in {"submitted", "under_review"}:
            row.status = "negotiated"
        self.s.commit()
        self.s.refresh(neg)
        if self._publish:
            self._publish(
                "claim.negotiated",
                {
                    "workspace_id": str(row.workspace_id),
                    "claim_id": str(row.id),
                    "round": next_round,
                    "status": status,
                },
            )
        return self._negotiation_dict(neg)

    def record_settlement(
        self,
        workspace_id,
        claim_id,
        *,
        outcome: str,
        settled_amount_minor: int,
        notes: str | None = None,
        recorded_by,
    ) -> dict:
        row = self._get_claim_row(workspace_id, claim_id)
        if outcome not in {"approved", "negotiated", "rejected", "withdrawn", "disputed"}:
            raise ClaimsError("bad_outcome")
        existing = self.s.scalar(
            select(ClaimSettlement).where(ClaimSettlement.claim_id == row.id)
        )
        if existing is not None:
            raise ClaimsError("settlement_exists")
        settlement = ClaimSettlement(
            workspace_id=row.workspace_id,
            claim_id=row.id,
            outcome=outcome,
            settled_amount_minor=settled_amount_minor,
            currency=row.currency,
            notes=notes,
            recorded_by=_to_uuid(recorded_by),
        )
        terminal_statuses = {
            "approved": "settled",
            "negotiated": "settled",
            "rejected": "settled",
            "withdrawn": "withdrawn",
            "disputed": "disputed",
        }
        row.status = terminal_statuses[outcome]
        row.recovered_amount_minor = settled_amount_minor
        row.settled_at = datetime.now(UTC)
        self.s.add(settlement)
        self.s.commit()
        self.s.refresh(settlement)
        if self._publish:
            self._publish(
                "claim.settled",
                {
                    "workspace_id": str(row.workspace_id),
                    "claim_id": str(row.id),
                    "outcome": outcome,
                    "recovered_amount_minor": settled_amount_minor,
                    "currency": row.currency,
                },
            )
        if self._outcomes_factory is not None:
            outcomes = self._outcomes_factory(self.s)
            if hasattr(outcomes, "record_claim_outcome"):
                try:
                    outcomes.record_claim_outcome(
                        row.workspace_id,
                        row.opportunity_id,
                        claim_id=row.id,
                        recovered_amount_minor=settled_amount_minor,
                        currency=row.currency,
                        recorded_by=recorded_by,
                    )
                except Exception:
                    pass
        return self._settlement_dict(settlement)

    def negotiation_timeline(self, workspace_id, claim_id) -> dict:
        row = self._get_claim_row(workspace_id, claim_id)
        responses = list(
            self.s.scalars(
                select(ClaimResponse)
                .where(
                    ClaimResponse.workspace_id == row.workspace_id,
                    ClaimResponse.claim_id == row.id,
                )
                .order_by(ClaimResponse.created_at.asc())
            )
        )
        negotiations = list(
            self.s.scalars(
                select(ClaimNegotiation)
                .where(
                    ClaimNegotiation.workspace_id == row.workspace_id,
                    ClaimNegotiation.claim_id == row.id,
                )
                .order_by(ClaimNegotiation.round.asc())
            )
        )
        settlement = self.s.scalar(
            select(ClaimSettlement).where(ClaimSettlement.claim_id == row.id)
        )
        return {
            "claim_id": str(row.id),
            "status": row.status,
            "responses": [self._response_dict(r) for r in responses],
            "negotiations": [self._negotiation_dict(n) for n in negotiations],
            "settlement": self._settlement_dict(settlement) if settlement else None,
        }

    # ---- drafts ------------------------------------------------------------

    def generate_draft(
        self, workspace_id, claim_id, draft_kind: str, *, created_by
    ) -> dict:
        row = self._get_claim_row(workspace_id, claim_id)
        if draft_kind not in _DRAFT_KINDS:
            raise ClaimsError("bad_draft_kind")
        body = self._draft_body(row, draft_kind)
        # Version is computed as next for this (claim_id, draft_kind).
        last = self.s.scalar(
            select(ClaimDraft)
            .where(
                ClaimDraft.workspace_id == row.workspace_id,
                ClaimDraft.claim_id == row.id,
                ClaimDraft.draft_kind == draft_kind,
            )
            .order_by(ClaimDraft.version.desc())
        )
        version = (last.version + 1) if last else 1
        draft = ClaimDraft(
            workspace_id=row.workspace_id,
            claim_id=row.id,
            draft_kind=draft_kind,
            status="draft",
            body=body,
            version=version,
            created_by=_to_uuid(created_by),
        )
        self.s.add(draft)
        self.s.commit()
        self.s.refresh(draft)
        return self._draft_dict(draft)

    def list_drafts(self, workspace_id, claim_id) -> list[dict]:
        row = self._get_claim_row(workspace_id, claim_id)
        rows = list(
            self.s.scalars(
                select(ClaimDraft)
                .where(
                    ClaimDraft.workspace_id == row.workspace_id,
                    ClaimDraft.claim_id == row.id,
                )
                .order_by(ClaimDraft.created_at.desc())
            )
        )
        return [self._draft_dict(d) for d in rows]

    def get_draft(self, workspace_id, draft_id) -> dict:
        wid = _to_uuid(workspace_id)
        row = self.s.scalar(
            select(ClaimDraft).where(
                ClaimDraft.id == _to_uuid(draft_id), ClaimDraft.workspace_id == wid
            )
        )
        if row is None:
            raise ClaimsError("not_found")
        return self._draft_dict(row)

    def approve_draft(self, workspace_id, draft_id, *, approved_by) -> dict:
        wid = _to_uuid(workspace_id)
        draft = self.s.scalar(
            select(ClaimDraft).where(
                ClaimDraft.id == _to_uuid(draft_id), ClaimDraft.workspace_id == wid
            )
        )
        if draft is None:
            raise ClaimsError("not_found")
        if draft.status != "draft":
            raise ClaimsError("bad_status_transition")
        draft.status = "approved"
        self.s.commit()
        self.s.refresh(draft)
        return self._draft_dict(draft)

    # ---- chain integrity / conflicts / metrics -----------------------------

    def chain_integrity(self, workspace_id, claim_id) -> dict:
        row = self._get_claim_row(workspace_id, claim_id)
        if row.change_event_id is None:
            return {"status": "chain_broken", "missing_link": "change_event"}
        if row.baseline_id is None:
            return {"status": "chain_broken", "missing_link": "baseline"}

        # Verify upstream exists when modules are available.
        event_ok = True
        baseline_ok = True
        if self._change_factory is not None:
            change = self._change_factory(self.s)
            if hasattr(change, "get_event"):
                try:
                    event = change.get_event(row.workspace_id, row.change_event_id)
                    if str(event.get("baseline_id")) != str(row.baseline_id):
                        return {"status": "chain_broken", "missing_link": "baseline_mismatch"}
                    if event.get("status") != "confirmed":
                        return {"status": "chain_broken", "missing_link": "event_not_confirmed"}
                except Exception:
                    event_ok = False
        if self._baseline_factory is not None:
            baseline = self._baseline_factory(self.s)
            if hasattr(baseline, "get"):
                try:
                    baseline_row = baseline.get(row.workspace_id, row.baseline_id)
                    if baseline_row is None:
                        baseline_ok = False
                except Exception:
                    baseline_ok = False
        if not event_ok:
            return {"status": "chain_broken", "missing_link": "change_event"}
        if not baseline_ok:
            return {"status": "chain_broken", "missing_link": "baseline"}
        return {"status": "intact"}

    def conflict_check(self, workspace_id, claim_id) -> dict:
        row = self._get_claim_row(workspace_id, claim_id)
        party = row.claimant_party
        if not party:
            return {
                "claim_id": str(row.id),
                "conflict_detected": False,
                "opposing_claims": [],
                "note": "no_party_marked",
            }
        opposers = _OPPOSING_PARTIES.get(party, frozenset())
        others = self.s.scalars(
            select(Claim).where(
                Claim.workspace_id == row.workspace_id,
                Claim.opportunity_id == row.opportunity_id,
                Claim.id != row.id,
            )
        ).all()
        conflicts = []
        for other in others:
            if other.claimant_party in opposers:
                conflicts.append(
                    {
                        "claim_id": str(other.id),
                        "title": other.title,
                        "claimant_party": other.claimant_party,
                    }
                )
        return {
            "claim_id": str(row.id),
            "conflict_detected": bool(conflicts),
            "opposing_claims": conflicts,
        }

    def cycle_metrics(self, workspace_id, opportunity_id) -> dict:
        wid = _to_uuid(workspace_id)
        oid = _to_uuid(opportunity_id)
        claims = list(
            self.s.scalars(
                select(Claim).where(Claim.workspace_id == wid, Claim.opportunity_id == oid)
            )
        )
        status_counts: dict[str, int] = {}
        cycle_times: list[dict] = []
        draft_to_submit: list[int] = []
        response_days: list[int] = []
        total_days: list[int] = []
        notice_timeliness: list[dict] = []
        recovered_total = 0
        claimed_total = 0
        for claim in claims:
            status_counts[claim.status] = status_counts.get(claim.status, 0) + 1
            submitted = claim.submitted_at
            settled = claim.settled_at
            claimed_total += claim.claim_amount_minor or 0
            if claim.status == "settled":
                recovered_total += claim.recovered_amount_minor or 0
            first_response = self.s.scalar(
                select(ClaimResponse.created_at)
                .where(ClaimResponse.claim_id == claim.id)
                .order_by(ClaimResponse.created_at.asc())
            )
            cycle_entry: dict[str, Any] = {"claim_id": str(claim.id), "status": claim.status}
            if submitted and claim.created_at:
                days = int((submitted - claim.created_at).total_seconds() / 86400)
                cycle_entry["draft_to_submit_days"] = days
                draft_to_submit.append(days)
            if first_response and submitted:
                days = int((first_response - submitted).total_seconds() / 86400)
                cycle_entry["response_days"] = days
                response_days.append(days)
            if settled and submitted:
                days = int((settled - submitted).total_seconds() / 86400)
                cycle_entry["total_days"] = days
                total_days.append(days)
            if submitted and claim.change_event_id:
                deadline = self._notice_deadline(wid, claim.change_event_id)
                if deadline:
                    deadline_dt = datetime.combine(deadline, time.min, tzinfo=UTC)
                    tl_days = int((submitted - deadline_dt).total_seconds() / 86400)
                    notice_timeliness.append(
                        {
                            "claim_id": str(claim.id),
                            "notice_deadline": deadline.isoformat(),
                            "submitted_at": submitted.isoformat(),
                            "timeliness_days": tl_days,
                            "on_time": tl_days <= 0,
                        }
                    )
                    cycle_entry["notice_timeliness_days"] = tl_days
                    cycle_entry["notice_on_time"] = tl_days <= 0
            cycle_times.append(cycle_entry)
        on_time_count = sum(1 for n in notice_timeliness if n["on_time"])
        late_count = len(notice_timeliness) - on_time_count
        return {
            "opportunity_id": str(oid),
            "status_counts": status_counts,
            "cycle_times": cycle_times,
            "averages": {
                "draft_to_submit_days": _avg(draft_to_submit),
                "response_days": _avg(response_days),
                "total_days": _avg(total_days),
            },
            "notice_timeliness": {
                "on_time": on_time_count,
                "late": late_count,
                "total": len(notice_timeliness),
                "on_time_rate_percent": _rate(on_time_count, len(notice_timeliness)),
                "details": notice_timeliness,
            },
            "recovered_total_minor": recovered_total,
            "claimed_total_minor": claimed_total,
        }

    def _notice_deadline(self, workspace_id, event_id) -> date | None:
        if self._change_factory is None:
            return None
        change = self._change_factory(self.s)
        if not hasattr(change, "notice_deadline_for_event"):
            return None
        try:
            payload = change.notice_deadline_for_event(workspace_id, event_id)
            deadline = payload.get("notice_deadline")
            if deadline:
                return date.fromisoformat(str(deadline))
        except Exception:
            pass
        return None

    # ---- helpers -----------------------------------------------------------

    def _get_claim_row(self, workspace_id, claim_id) -> Claim:
        row = self.s.scalar(
            select(Claim).where(
                Claim.id == _to_uuid(claim_id),
                Claim.workspace_id == _to_uuid(workspace_id),
            )
        )
        if row is None:
            raise ClaimsError("not_found")
        return row

    def _chronology_rows(self, claim_id: uuid.UUID, opportunity_id: uuid.UUID) -> list[dict]:
        rows = list(
            self.s.scalars(
                select(ClaimChronologyEntry)
                .where(ClaimChronologyEntry.claim_id == claim_id)
                .order_by(ClaimChronologyEntry.occurred_at.asc())
            )
        )
        return [
            {
                "id": str(r.id),
                "claim_id": str(r.claim_id),
                "opportunity_id": str(opportunity_id),
                "entry_type": r.entry_type,
                "source_kind": r.source_kind,
                "source_id": str(r.source_id) if r.source_id else None,
                "title": r.title,
                "occurred_at": r.occurred_at.isoformat(),
                "source_page": r.source_page,
                "source_quote": r.source_quote,
                "document_id": str(r.document_id) if r.document_id else None,
                "custody_chain": r.custody_chain or [],
            }
            for r in rows
        ]

    def _claim_dict(self, row: Claim) -> dict:
        return {
            "id": str(row.id),
            "opportunity_id": str(row.opportunity_id),
            "change_event_id": str(row.change_event_id) if row.change_event_id else None,
            "baseline_id": str(row.baseline_id) if row.baseline_id else None,
            "claim_type": row.claim_type,
            "claimant_party": row.claimant_party,
            "status": row.status,
            "title": row.title,
            "description": row.description,
            "claim_amount_minor": row.claim_amount_minor,
            "recovered_amount_minor": row.recovered_amount_minor,
            "currency": row.currency,
            "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
            "submitted_by": str(row.submitted_by) if row.submitted_by else None,
            "approved_by": str(row.approved_by) if row.approved_by else None,
            "settled_at": row.settled_at.isoformat() if row.settled_at else None,
            "created_by": str(row.created_by),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    def _enriched_claim_dict(self, row: Claim) -> dict:
        d = self._claim_dict(row)
        d["completeness_score"] = _completeness_score(self.s, row)
        d["chain_integrity"] = self.chain_integrity(row.workspace_id, row.id)["status"]
        return d

    def _checklist_item_dict(self, item: ClaimEvidenceChecklistItem) -> dict:
        return {
            "id": str(item.id),
            "claim_id": str(item.claim_id),
            "item_type": item.item_type,
            "required": item.required,
            "present": item.present,
            "evidence_record_ids": item.evidence_record_ids or [],
            "override_note": item.override_note,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }

    def _line_item_dict(self, item: ClaimQuantumLineItem) -> dict:
        measured_total = int(Decimal(str(item.quantity)) * item.rate_minor)
        daywork_total = 0
        if item.daywork_days and item.daywork_rate_minor:
            daywork_total = item.daywork_days * item.daywork_rate_minor
        return {
            "id": str(item.id),
            "claim_id": str(item.claim_id),
            "cost_code_id": str(item.cost_code_id) if item.cost_code_id else None,
            "description": item.description,
            "quantity": str(item.quantity),
            "unit": item.unit,
            "rate_minor": item.rate_minor,
            "measured_total_minor": measured_total,
            "daywork_days": item.daywork_days,
            "daywork_rate_minor": item.daywork_rate_minor,
            "daywork_total_minor": daywork_total,
            "total_minor": measured_total + daywork_total,
            "currency": item.currency,
            "created_by": str(item.created_by),
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }

    def _delay_event_dict(self, row: ClaimDelayEvent) -> dict:
        return {
            "id": str(row.id),
            "opportunity_id": str(row.opportunity_id),
            "claim_id": str(row.claim_id) if row.claim_id else None,
            "change_event_id": str(row.change_event_id) if row.change_event_id else None,
            "event_date": row.event_date.isoformat() if row.event_date else None,
            "description": row.description,
            "delay_days": row.delay_days,
            "programme_activity": row.programme_activity,
            "source_page": row.source_page,
            "source_quote": row.source_quote,
            "document_id": str(row.document_id) if row.document_id else None,
            "created_by": str(row.created_by),
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    def _response_dict(self, row: ClaimResponse) -> dict:
        return {
            "id": str(row.id),
            "claim_id": str(row.claim_id),
            "response_kind": row.response_kind,
            "received_at": row.received_at.isoformat() if row.received_at else None,
            "due_at": row.due_at.isoformat() if row.due_at else None,
            "responder": row.responder,
            "notes": row.notes,
            "document_id": str(row.document_id) if row.document_id else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    def _negotiation_dict(self, row: ClaimNegotiation) -> dict:
        return {
            "id": str(row.id),
            "claim_id": str(row.claim_id),
            "round": row.round,
            "offered_amount_minor": row.offered_amount_minor,
            "counter_amount_minor": row.counter_amount_minor,
            "status": row.status,
            "recorded_by": str(row.recorded_by),
            "recorded_at": row.recorded_at.isoformat() if row.recorded_at else None,
        }

    def _settlement_dict(self, row: ClaimSettlement) -> dict:
        return {
            "id": str(row.id),
            "claim_id": str(row.claim_id),
            "outcome": row.outcome,
            "settled_amount_minor": row.settled_amount_minor,
            "currency": row.currency,
            "notes": row.notes,
            "recorded_by": str(row.recorded_by),
            "recorded_at": row.recorded_at.isoformat() if row.recorded_at else None,
        }

    def _draft_dict(self, row: ClaimDraft) -> dict:
        return {
            "id": str(row.id),
            "claim_id": str(row.claim_id),
            "draft_kind": row.draft_kind,
            "status": row.status,
            "body": row.body or {},
            "version": row.version,
            "created_by": str(row.created_by),
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    def _draft_body(self, row: Claim, draft_kind: str) -> dict:
        chronology = self.chronology_for_claim(row.workspace_id, row.id)
        quantum = self.quantum_for_claim(row.workspace_id, row.id)
        checklist = self.checklist_for_claim(row.workspace_id, row.id)
        body = {
            "draft_kind": draft_kind,
            "claim": self._claim_dict(row),
            "chronology": chronology,
            "quantum": quantum,
            "checklist": checklist,
            "delay_register": [
                self._delay_event_dict(d)
                for d in list(
                    self.s.scalars(
                        select(ClaimDelayEvent).where(
                            ClaimDelayEvent.workspace_id == row.workspace_id,
                            ClaimDelayEvent.claim_id == row.id,
                        )
                    )
                )
            ],
        }
        if draft_kind == "particulars":
            body["narrative"] = (
                f"Particulars of claim for {row.title} based on the cited chronology."
            )
        elif draft_kind == "variation_proposal":
            body["narrative"] = f"Variation proposal for {row.title} with quantum summary."
        elif draft_kind == "eot":
            body["narrative"] = (
                f"Extension of time narrative for {row.title} with delay events."
            )
        elif draft_kind == "full_pack":
            body["narrative"] = (
                f"Full claim package for {row.title} including chronology, quantum and delays."
            )
        return body


# ---- module-level helpers -------------------------------------------------


def _ensure_checklist(session: Session, workspace_id: uuid.UUID, claim: Claim) -> None:
    required = _CLAIM_TYPE_CHECKLIST.get(claim.claim_type, set())
    existing = {
        item.item_type: item
        for item in session.scalars(
            select(ClaimEvidenceChecklistItem).where(
                ClaimEvidenceChecklistItem.workspace_id == workspace_id,
                ClaimEvidenceChecklistItem.claim_id == claim.id,
            )
        )
    }
    for item_type in required:
        if item_type not in existing:
            session.add(
                ClaimEvidenceChecklistItem(
                    workspace_id=workspace_id,
                    claim_id=claim.id,
                    item_type=item_type,
                    required=True,
                    present=False,
                    evidence_record_ids=[],
                )
            )
    session.commit()


def _refresh_checklist(
    session: Session,
    claim: Claim,
    *,
    evidence_records: list[dict],
    line_items: list[ClaimQuantumLineItem],
    delay_events: list[ClaimDelayEvent],
) -> None:
    # Build a map of checklist item -> [evidence ids]
    evidence_map: dict[str, list[str]] = {}
    for rec in evidence_records:
        record_id = rec.get("id")
        record_type = rec.get("record_type")
        for item_type in _EVIDENCE_ITEM_MAP.get(record_type, set()):
            evidence_map.setdefault(item_type, []).append(record_id)

    # Baseline satisfied by claim.baseline_id.
    if claim.baseline_id:
        evidence_map.setdefault("baseline", []).append(str(claim.baseline_id))

    # Quantum satisfied by line items or measurement evidence.
    if line_items:
        evidence_map.setdefault("quantum", []).extend([str(i.id) for i in line_items])

    # Delay satisfied by delay events.
    if delay_events:
        evidence_map.setdefault("delay", []).extend([str(d.id) for d in delay_events])
        evidence_map.setdefault("schedule", []).extend([str(d.id) for d in delay_events])

    items = list(
        session.scalars(
            select(ClaimEvidenceChecklistItem).where(
                ClaimEvidenceChecklistItem.workspace_id == claim.workspace_id,
                ClaimEvidenceChecklistItem.claim_id == claim.id,
            )
        )
    )
    for item in items:
        if item.override_note:
            # User has explicitly overridden; keep present=True.
            item.present = True
            continue
        ids = evidence_map.get(item.item_type, [])
        item.present = bool(ids)
        item.evidence_record_ids = ids
    session.commit()


def _completeness_score(session: Session, claim: Claim) -> int:
    items = list(
        session.scalars(
            select(ClaimEvidenceChecklistItem).where(
                ClaimEvidenceChecklistItem.workspace_id == claim.workspace_id,
                ClaimEvidenceChecklistItem.claim_id == claim.id,
            )
        )
    )
    if not items:
        return 0
    present = sum(1 for i in items if i.present)
    return int(100 * present / len(items))


def _event_entry(event: dict, claim_id: uuid.UUID, opportunity_id: uuid.UUID) -> dict:
    occurred = _event_occurred_at(event)
    return {
        "id": str(uuid.uuid4()),
        "claim_id": str(claim_id),
        "opportunity_id": str(opportunity_id),
        "entry_type": "event",
        "source_kind": "change_event",
        "source_id": event.get("id"),
        "title": f"Change event: {event.get('title', '')}",
        "occurred_at": occurred.isoformat(),
        "source_page": None,
        "source_quote": None,
        "document_id": None,
        "custody_chain": [],
    }


def _source_entry(
    source: dict, event: dict, claim_id: uuid.UUID, opportunity_id: uuid.UUID
) -> dict:
    received = source.get("received_at")
    occurred = (
        _as_utc(datetime.fromisoformat(received))
        if received
        else _event_occurred_at(event)
    )
    return {
        "id": str(uuid.uuid4()),
        "claim_id": str(claim_id),
        "opportunity_id": str(opportunity_id),
        "entry_type": "notice",
        "source_kind": "change_source",
        "source_id": source.get("id"),
        "title": f"Source: {source.get('source_kind', 'unknown')}",
        "occurred_at": occurred.isoformat(),
        "source_page": source.get("source_page"),
        "source_quote": source.get("source_quote"),
        "document_id": source.get("document_id"),
        "custody_chain": [],
    }


def _evidence_entry(record: dict, claim_id: uuid.UUID, opportunity_id: uuid.UUID) -> dict:
    captured = record.get("captured_at")
    return {
        "id": str(uuid.uuid4()),
        "claim_id": str(claim_id),
        "opportunity_id": str(opportunity_id),
        "entry_type": "evidence",
        "source_kind": "evidence_record",
        "source_id": record.get("id"),
        "title": f"Evidence: {record.get('title', '')} ({record.get('record_type', '')})",
        "occurred_at": captured if captured else datetime.now(UTC).isoformat(),
        "source_page": None,
        "source_quote": None,
        "document_id": record.get("document_id"),
        "custody_chain": record.get("custody_chain") or [],
    }


def _event_occurred_at(event: dict) -> datetime:
    trigger = event.get("trigger_date")
    if trigger:
        try:
            return _as_utc(datetime.fromisoformat(trigger)) or datetime.now(UTC)
        except Exception:
            pass
    created = event.get("created_at")
    if created:
        try:
            return _as_utc(datetime.fromisoformat(created)) or datetime.now(UTC)
        except Exception:
            pass
    return datetime.now(UTC)
