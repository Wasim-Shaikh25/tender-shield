"""Control tower — portfolio exposure and project dashboards (TS-272, TS-273)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session


class ControlTowerError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class ControlTowerService:
    def __init__(
        self,
        session: Session,
        *,
        ingestion_factory: Callable | None = None,
        claims_factory: Callable | None = None,
        change_factory: Callable | None = None,
        evidence_factory: Callable | None = None,
        outcomes_factory: Callable | None = None,
        publish: Callable | None = None,
    ):
        self.s = session
        self._ingestion_factory = ingestion_factory
        self._claims_factory = claims_factory
        self._change_factory = change_factory
        self._evidence_factory = evidence_factory
        self._outcomes_factory = outcomes_factory
        self._publish = publish

    def exposure_for_opportunity(
        self,
        workspace_id,
        opportunity_id,
        *,
        cost_of_capital_pa: float = 0.12,
        currency: str = "INR",
    ) -> dict:
        ws = uuid.UUID(str(workspace_id))
        oid = uuid.UUID(str(opportunity_id))

        opportunity = self._get_opportunity(ws, oid)
        if opportunity is None:
            raise ControlTowerError("opportunity_not_found")

        contract_value_minor = getattr(opportunity, "contract_value_minor", None)
        contract_currency = getattr(opportunity, "currency", currency)

        claims = self._claims_summary(ws, oid)
        events = self._change_events(ws, oid)

        today = date.today()
        daily_rate = Decimal(str(cost_of_capital_pa)) / Decimal(365)

        submitted = 0
        certified = 0
        rejected = 0
        unnotified = 0
        cash_exposure = 0
        ageing_days: list[int] = []

        submitted_event_ids = set()

        for claim in claims:
            if claim.get("currency") != contract_currency:
                continue
            amount = self._int_or(claim.get("claim_amount_minor"), 0)
            recovered = self._int_or(claim.get("recovered_amount_minor"), 0)
            status = claim.get("status")
            submitted_at = self._as_date(claim.get("submitted_at"))

            if status in {"submitted", "under_review", "negotiated", "disputed"}:
                submitted += amount
                age = (today - submitted_at).days if submitted_at else 0
                if age > 0:
                    ageing_days.append(age)
                    cash_exposure += int(
                        Decimal(amount) * Decimal(age) * daily_rate
                    )
            elif status == "settled":
                certified += recovered
            elif status in {"rejected", "withdrawn"}:
                rejected += amount

            if status == "draft" and claim.get("change_event_id"):
                unnotified += amount
            if claim.get("change_event_id") and status not in {"draft"}:
                submitted_event_ids.add(claim.get("change_event_id"))

        unclaimed_events = [
            e for e in events
            if str(e.get("id")) not in submitted_event_ids
            and e.get("status") == "confirmed"
        ]

        at_risk = None
        if contract_value_minor is not None and contract_currency == currency:
            at_risk = int(max(contract_value_minor - certified, 0))

        summary = {
            "opportunity_id": str(oid),
            "currency": contract_currency,
            "contract_value_minor": contract_value_minor,
            "at_risk_revenue_minor": at_risk,
            "submitted_minor": submitted,
            "certified_minor": certified,
            "rejected_minor": rejected,
            "unnotified_change_minor": unnotified,
            "unclaimed_change_events": len(unclaimed_events),
            "age_days_avg": int(sum(ageing_days) / len(ageing_days)) if ageing_days else 0,
            "age_days_max": max(ageing_days) if ageing_days else 0,
            "cash_exposure_minor": cash_exposure,
            "cost_of_capital_pa": cost_of_capital_pa,
        }

        if self._publish:
            self._publish(
                "controltower.exposure_computed",
                {
                    "workspace_id": str(ws),
                    "opportunity_id": str(oid),
                    "currency": contract_currency,
                    "submitted_minor": submitted,
                    "certified_minor": certified,
                },
            )

        return summary

    def dashboard_for_opportunity(
        self,
        workspace_id,
        opportunity_id,
        *,
        currency: str = "INR",
    ) -> dict:
        ws = uuid.UUID(str(workspace_id))
        oid = uuid.UUID(str(opportunity_id))

        opportunity = self._get_opportunity(ws, oid)
        if opportunity is None:
            raise ControlTowerError("opportunity_not_found")

        deadlines = self._deadlines(ws, oid)
        events = self._change_events(ws, oid)

        deadline_rows: list[dict] = []
        today = date.today()
        for d in deadlines:
            due = self._as_datetime(getattr(d, "due_at", None))
            if due is None:
                continue
            due_date = due.date()
            delta = (due_date - today).days
            if delta < 0:
                status = "overdue"
            elif delta < 7:
                status = "due_soon"
            else:
                status = "ok"
            deadline_rows.append(
                {
                    "id": str(d.id),
                    "kind": getattr(d, "kind", None),
                    "due_at": due.isoformat() if due else None,
                    "description": getattr(d, "description", None),
                    "confirmed": getattr(d, "confirmed", False),
                    "status": status,
                }
            )

        evidence_scores: list[int] = []
        unclaimed_events: list[dict] = []
        event_health: list[dict] = []
        for e in events:
            eid = str(e.get("id"))
            completeness = None
            if self._evidence_factory is not None:
                try:
                    ev = self._evidence_factory(self.s)
                    if hasattr(ev, "completeness_for_event"):
                        completeness = ev.completeness_for_event(ws, eid)
                        if isinstance(completeness, dict):
                            score = completeness.get("score", 0)
                        else:
                            score = 0
                        evidence_scores.append(score)
                except Exception:
                    pass
            linked = any(
                c.get("change_event_id") == eid
                for c in self._claims_summary(ws, oid)
                if c.get("status") != "draft"
            )
            if e.get("status") == "confirmed" and not linked:
                unclaimed_events.append(
                    {
                        "id": eid,
                        "title": e.get("title"),
                        "notice_deadline": e.get("notice_deadline"),
                    }
                )
            if completeness is not None:
                event_health.append(
                    {
                        "event_id": eid,
                        "title": e.get("title"),
                        "evidence_completeness": completeness,
                    }
                )

        avg_score = (
            int(sum(evidence_scores) / len(evidence_scores))
            if evidence_scores else 100
        )

        return {
            "opportunity_id": str(oid),
            "deadlines": sorted(deadline_rows, key=lambda x: x["due_at"] or ""),
            "evidence_health_score": avg_score,
            "evidence_health_events": event_health,
            "unclaimed_change_events": unclaimed_events,
            "unavailable": {
                "ingestion": self._ingestion_factory is None,
                "change": self._change_factory is None,
                "claims": self._claims_factory is None,
                "evidence": self._evidence_factory is None,
            },
        }

    def portfolio_summary(
        self,
        workspace_id,
        *,
        cost_of_capital_pa: float = 0.12,
        currency: str = "INR",
    ) -> dict:
        ws = uuid.UUID(str(workspace_id))
        opps = self._list_opportunities(ws)

        total_contract_value = 0
        total_submitted = 0
        total_certified = 0
        total_rejected = 0
        total_unnotified = 0
        total_cash_exposure = 0
        opportunities_healthy = 0
        opportunities_at_risk = 0
        opportunities_poor = 0
        opportunity_snapshots: list[dict] = []

        for opp in opps:
            oid = opp.id
            snapshot = {
                "opportunity_id": str(oid),
                "title": getattr(opp, "title", None),
            }
            try:
                exposure = self.exposure_for_opportunity(
                    ws, oid, cost_of_capital_pa=cost_of_capital_pa, currency=currency
                )
                snapshot["exposure"] = exposure
                total_submitted += exposure.get("submitted_minor", 0)
                total_certified += exposure.get("certified_minor", 0)
                total_rejected += exposure.get("rejected_minor", 0)
                total_unnotified += exposure.get("unnotified_change_minor", 0)
                total_cash_exposure += exposure.get("cash_exposure_minor", 0)
                cv = exposure.get("contract_value_minor")
                if cv is not None:
                    total_contract_value += cv

                dashboard = self.dashboard_for_opportunity(ws, oid, currency=currency)
                score = dashboard.get("evidence_health_score", 100)
                if score >= 80:
                    opportunities_healthy += 1
                elif score >= 50:
                    opportunities_at_risk += 1
                else:
                    opportunities_poor += 1
                snapshot["dashboard"] = dashboard
            except Exception:
                snapshot["exposure"] = None
                snapshot["dashboard"] = None
            opportunity_snapshots.append(snapshot)

        margin = None
        if self._outcomes_factory is not None:
            try:
                outcomes = self._outcomes_factory(self.s)
                if hasattr(outcomes, "margin_protected"):
                    margin = outcomes.margin_protected(ws, currency=currency)
            except Exception:
                pass

        return {
            "workspace_id": str(ws),
            "currency": currency,
            "opportunities_count": len(opps),
            "total_contract_value_minor": total_contract_value,
            "total_submitted_minor": total_submitted,
            "total_certified_minor": total_certified,
            "total_rejected_minor": total_rejected,
            "total_unnotified_change_minor": total_unnotified,
            "total_cash_exposure_minor": total_cash_exposure,
            "opportunities_healthy": opportunities_healthy,
            "opportunities_at_risk": opportunities_at_risk,
            "opportunities_poor": opportunities_poor,
            "margin_protected": margin,
            "opportunities": opportunity_snapshots,
        }

    def _get_opportunity(self, workspace_id: uuid.UUID, opportunity_id: uuid.UUID) -> Any | None:
        if self._ingestion_factory is None:
            raise ControlTowerError("ingestion_unavailable")
        ingestion = self._ingestion_factory(self.s)
        if not hasattr(ingestion, "get_opportunity"):
            raise ControlTowerError("ingestion_unavailable")
        return ingestion.get_opportunity(workspace_id, opportunity_id)

    def _list_opportunities(self, workspace_id: uuid.UUID) -> list[Any]:
        if self._ingestion_factory is None:
            return []
        ingestion = self._ingestion_factory(self.s)
        if not hasattr(ingestion, "list_opportunities"):
            return []
        return ingestion.list_opportunities(workspace_id)

    def _claims_summary(self, workspace_id: uuid.UUID, opportunity_id: uuid.UUID) -> list[dict]:
        if self._claims_factory is None:
            return []
        claims = self._claims_factory(self.s)
        if not hasattr(claims, "list_claim_summaries"):
            return []
        return claims.list_claim_summaries(workspace_id, opportunity_id)

    def _change_events(self, workspace_id: uuid.UUID, opportunity_id: uuid.UUID) -> list[dict]:
        if self._change_factory is None:
            return []
        change = self._change_factory(self.s)
        if not hasattr(change, "list_events"):
            return []
        return change.list_events(workspace_id, opportunity_id)

    def _deadlines(self, workspace_id: uuid.UUID, opportunity_id: uuid.UUID) -> list[Any]:
        if self._ingestion_factory is None:
            return []
        ingestion = self._ingestion_factory(self.s)
        if not hasattr(ingestion, "list_deadlines"):
            return []
        return ingestion.list_deadlines(workspace_id, opportunity_id)

    @staticmethod
    def _int_or(value: Any, default: int) -> int:
        try:
            return int(value) if value is not None else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _as_date(value: Any) -> date | None:
        if value is None:
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        try:
            return date.fromisoformat(str(value)[:10])
        except Exception:
            return None

    @staticmethod
    def _as_datetime(value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value))
        except Exception:
            return None
