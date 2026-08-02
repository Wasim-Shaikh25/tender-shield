"""Subcontract control service (TS-288, TS-289)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.subcontract.models import (
    Subcontract,
    SubcontractClause,
    SubcontractPaymentEvent,
    SubcontractScopeItem,
)


class SubcontractError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class SubcontractService:
    def __init__(
        self,
        session: Session,
        *,
        baseline_factory: Callable[[Session], object] | None = None,
        change_factory: Callable[[Session], object] | None = None,
        publish: Callable[[str, dict], Any] | None = None,
    ) -> None:
        self.s = session
        self._baseline_factory = baseline_factory
        self._change_factory = change_factory
        self._publish = publish or (lambda event, payload: None)

    def _baseline(self):
        if self._baseline_factory is None:
            raise SubcontractError("baseline_unavailable")
        return self._baseline_factory(self.s)

    def _change(self):
        if self._change_factory is None:
            raise SubcontractError("change_unavailable")
        return self._change_factory(self.s)

    def create_subcontract(
        self,
        workspace_id,
        opportunity_id,
        *,
        subcontractor_name: str,
        created_by,
        reference: str | None = None,
        contract_value_minor: int | None = None,
        currency: str = "INR",
        scope: str | None = None,
        notice_buffer_days: int = 7,
        postal_buffer_days: int = 2,
    ) -> Subcontract:
        row = Subcontract(
            workspace_id=uuid.UUID(str(workspace_id)),
            opportunity_id=uuid.UUID(str(opportunity_id)),
            subcontractor_name=subcontractor_name,
            reference=reference,
            contract_value_minor=contract_value_minor,
            currency=currency,
            scope=scope,
            notice_buffer_days=notice_buffer_days,
            postal_buffer_days=postal_buffer_days,
            created_by=uuid.UUID(str(created_by)),
        )
        self.s.add(row)
        self.s.commit()
        self.s.refresh(row)
        return row

    def list_subcontracts(self, workspace_id, opportunity_id) -> list[Subcontract]:
        return list(
            self.s.scalars(
                select(Subcontract).where(
                    Subcontract.workspace_id == uuid.UUID(str(workspace_id)),
                    Subcontract.opportunity_id == uuid.UUID(str(opportunity_id)),
                )
            )
        )

    def get_subcontract(self, workspace_id, subcontract_id) -> Subcontract:
        row = self.s.scalar(
            select(Subcontract).where(
                Subcontract.id == uuid.UUID(str(subcontract_id)),
                Subcontract.workspace_id == uuid.UUID(str(workspace_id)),
            )
        )
        if row is None:
            raise SubcontractError("not_found")
        return row

    def add_clause(
        self,
        workspace_id,
        subcontract_id,
        *,
        title: str,
        source_quote: str | None = None,
        present: bool | None = None,
        status: str = "unchecked",
    ) -> SubcontractClause:
        subcontract = self.get_subcontract(workspace_id, subcontract_id)
        row = SubcontractClause(
            workspace_id=uuid.UUID(str(workspace_id)),
            subcontract_id=subcontract.id,
            title=title,
            source_quote=source_quote,
            present=present,
            status=status,
        )
        self.s.add(row)
        self.s.commit()
        self.s.refresh(row)
        return row

    def add_scope_item(
        self,
        workspace_id,
        subcontract_id,
        *,
        item_text: str,
        covered: bool = False,
        source_event_id: str | None = None,
    ) -> SubcontractScopeItem:
        subcontract = self.get_subcontract(workspace_id, subcontract_id)
        row = SubcontractScopeItem(
            workspace_id=uuid.UUID(str(workspace_id)),
            subcontract_id=subcontract.id,
            item_text=item_text,
            covered=covered,
            source_event_id=uuid.UUID(str(source_event_id)) if source_event_id else None,
        )
        self.s.add(row)
        self.s.commit()
        self.s.refresh(row)
        return row

    def flowdown_check(self, workspace_id, subcontract_id) -> dict:
        subcontract = self.get_subcontract(workspace_id, subcontract_id)
        main_clauses = self._main_contract_clauses(workspace_id, subcontract.opportunity_id)
        main_titles = {c["title"].lower().strip() for c in main_clauses if c.get("title")}

        clauses = self.s.scalars(
            select(SubcontractClause).where(
                SubcontractClause.subcontract_id == subcontract.id,
                SubcontractClause.workspace_id == uuid.UUID(str(workspace_id)),
            )
        ).all()

        matched = []
        missing = []
        for clause in clauses:
            title = clause.title.lower().strip()
            if title in main_titles:
                matched.append({"id": str(clause.id), "title": clause.title})
            else:
                missing.append({"id": str(clause.id), "title": clause.title})

        sub_titles = {c.title.lower().strip() for c in clauses}
        missing_in_sub = [
            {"title": c["title"], "source_quote": c.get("source_quote")}
            for c in main_clauses
            if c.get("title") and c["title"].lower().strip() not in sub_titles
        ]

        return {
            "subcontract_id": str(subcontract_id),
            "matched": matched,
            "missing": missing,
            "missing_in_subcontract": missing_in_sub,
        }

    def _main_contract_clauses(self, workspace_id, opportunity_id) -> list[dict]:
        try:
            baseline = self._baseline().latest(workspace_id, opportunity_id)
            if baseline and baseline.snapshot:
                return baseline.snapshot.get("clauses") or []
        except Exception:
            pass
        return []

    def scope_gaps(self, workspace_id, subcontract_id) -> dict:
        subcontract = self.get_subcontract(workspace_id, subcontract_id)
        main_scope = (subcontract.scope or "").lower()
        try:
            baseline = self._baseline().latest(workspace_id, subcontract.opportunity_id)
            if baseline and baseline.snapshot:
                scope_text = baseline.snapshot.get("opportunity", {}).get("scope", "") or ""
                main_scope += " " + scope_text.lower()
        except Exception:
            pass

        try:
            events = self._change().list_events(workspace_id, subcontract.opportunity_id)
            event_text = " ".join((e.get("title") or "").lower() for e in events)
            main_scope += " " + event_text
        except Exception:
            pass

        items = self.s.scalars(
            select(SubcontractScopeItem).where(
                SubcontractScopeItem.subcontract_id == subcontract.id,
                SubcontractScopeItem.workspace_id == uuid.UUID(str(workspace_id)),
            )
        ).all()

        gaps = []
        covered = []
        for item in items:
            text = item.item_text.lower().strip()
            if text and text in main_scope:
                covered.append({"id": str(item.id), "item_text": item.item_text})
            else:
                gaps.append({"id": str(item.id), "item_text": item.item_text})

        return {"subcontract_id": str(subcontract_id), "gaps": gaps, "covered": covered}

    def notice_calendar(self, workspace_id, subcontract_id) -> dict:
        subcontract = self.get_subcontract(workspace_id, subcontract_id)
        try:
            events = self._change().list_events(workspace_id, subcontract.opportunity_id)
        except Exception:
            events = []

        buffer = timedelta(days=subcontract.notice_buffer_days + subcontract.postal_buffer_days)
        calendar = []
        for event in events:
            deadline = event.get("notice_deadline")
            if not deadline:
                continue
            if isinstance(deadline, str):
                try:
                    deadline = datetime.fromisoformat(deadline).date()
                except ValueError:
                    continue
            if isinstance(deadline, datetime):
                deadline = deadline.date()
            sub_deadline = deadline - buffer
            today = datetime.now(UTC).date()
            status = "ok"
            if sub_deadline < today:
                status = "overdue"
            elif (sub_deadline - today).days <= 7:
                status = "due_soon"
            calendar.append(
                {
                    "change_event_id": event.get("id"),
                    "main_deadline": deadline.isoformat(),
                    "subcontract_deadline": sub_deadline.isoformat(),
                    "status": status,
                }
            )

        return {"subcontract_id": str(subcontract_id), "calendar": calendar}

    def add_payment_event(
        self,
        workspace_id,
        subcontract_id,
        *,
        kind: str,
        due_date: date,
        amount_minor: int,
        certified_amount_minor: int | None = None,
        currency: str = "INR",
        status: str = "pending",
        parent_payment_status: str | None = None,
    ) -> SubcontractPaymentEvent:
        subcontract = self.get_subcontract(workspace_id, subcontract_id)
        row = SubcontractPaymentEvent(
            workspace_id=uuid.UUID(str(workspace_id)),
            subcontract_id=subcontract.id,
            kind=kind,
            due_date=due_date,
            amount_minor=amount_minor,
            certified_amount_minor=certified_amount_minor,
            currency=currency,
            status=status,
            parent_payment_status=parent_payment_status,
        )
        self.s.add(row)
        self.s.commit()
        self.s.refresh(row)
        return row

    def payment_exposure(self, workspace_id, subcontract_id) -> dict:
        subcontract = self.get_subcontract(workspace_id, subcontract_id)
        events = self.s.scalars(
            select(SubcontractPaymentEvent).where(
                SubcontractPaymentEvent.subcontract_id == subcontract.id,
                SubcontractPaymentEvent.workspace_id == uuid.UUID(str(workspace_id)),
            )
        ).all()

        total_certified = 0
        total_paid = 0
        pending = 0
        age_days_max = 0
        pay_when_paid_exposed = 0
        today = datetime.now(UTC).date()

        for event in events:
            certified = event.certified_amount_minor or 0
            total_certified += certified
            if event.status == "paid":
                total_paid += certified
            else:
                pending += certified
                age = (today - event.due_date).days if event.due_date else 0
                if age > age_days_max:
                    age_days_max = age
                if event.parent_payment_status != "received":
                    pay_when_paid_exposed += certified

        return {
            "subcontract_id": str(subcontract_id),
            "currency": subcontract.currency,
            "total_certified_minor": total_certified,
            "total_paid_minor": total_paid,
            "pending_minor": pending,
            "age_days_max": age_days_max,
            "pay_when_paid_exposed_minor": pay_when_paid_exposed,
        }

    def _subcontract_dict(self, row: Subcontract) -> dict:
        return {
            "id": str(row.id),
            "opportunity_id": str(row.opportunity_id),
            "subcontractor_name": row.subcontractor_name,
            "reference": row.reference,
            "contract_value_minor": row.contract_value_minor,
            "currency": row.currency,
            "scope": row.scope,
            "notice_buffer_days": row.notice_buffer_days,
            "postal_buffer_days": row.postal_buffer_days,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
