"""Control tower — portfolio exposure and project dashboards (TS-272–TS-280)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.controltower.models import CtPaymentEvent


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
        findings_factory: Callable | None = None,
        outcomes_factory: Callable | None = None,
        billing_factory: Callable | None = None,
        publish: Callable | None = None,
    ):
        self.s = session
        self._ingestion_factory = ingestion_factory
        self._claims_factory = claims_factory
        self._change_factory = change_factory
        self._evidence_factory = evidence_factory
        self._findings_factory = findings_factory
        self._outcomes_factory = outcomes_factory
        self._billing_factory = billing_factory
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

    def forecast_for_opportunity(
        self,
        workspace_id,
        opportunity_id,
        *,
        projected_final_cost_minor: int,
        contingency_percent: float = 0.0,
        cost_of_capital_pa: float = 0.12,
        currency: str = "INR",
    ) -> dict:
        ws = uuid.UUID(str(workspace_id))
        oid = uuid.UUID(str(opportunity_id))
        opportunity = self._get_opportunity(ws, oid)
        if opportunity is None:
            raise ControlTowerError("opportunity_not_found")

        exposure = self.exposure_for_opportunity(
            ws, oid, cost_of_capital_pa=cost_of_capital_pa, currency=currency
        )

        contract_value = getattr(opportunity, "contract_value_minor", None)
        contract_currency = getattr(opportunity, "currency", currency)

        forecast_revenue = None
        if contract_value is not None and contract_currency == currency:
            forecast_revenue = max(int(contract_value - exposure["submitted_minor"]), 0)

        contingency_multiplier = Decimal(1) + Decimal(str(contingency_percent)) / Decimal(100)
        forecast_cost = int(
            Decimal(projected_final_cost_minor) * contingency_multiplier
            + Decimal(exposure["unnotified_change_minor"])
            + Decimal(exposure["cash_exposure_minor"])
        )

        assumptions = {
            "projected_final_cost_minor": projected_final_cost_minor,
            "contingency_percent": contingency_percent,
            "cost_of_capital_pa": cost_of_capital_pa,
            "currency": currency,
            "contract_value_minor": contract_value,
            "contract_currency": contract_currency,
            "exposure_submitted_minor": exposure["submitted_minor"],
            "exposure_certified_minor": exposure["certified_minor"],
            "exposure_unnotified_change_minor": exposure["unnotified_change_minor"],
            "exposure_cash_exposure_minor": exposure["cash_exposure_minor"],
        }

        if self._publish:
            self._publish(
                "controltower.forecast_computed",
                {
                    "workspace_id": str(ws),
                    "opportunity_id": str(oid),
                    "forecast_revenue_minor": forecast_revenue,
                    "forecast_cost_minor": forecast_cost,
                },
            )

        return {
            "opportunity_id": str(oid),
            "currency": currency,
            "forecast_revenue_minor": forecast_revenue,
            "forecast_cost_minor": forecast_cost,
            "forecast_margin_minor": (
                forecast_revenue - forecast_cost if forecast_revenue is not None else None
            ),
            "assumptions": assumptions,
        }

    def response_times_for_opportunity(self, workspace_id, opportunity_id) -> dict:
        ws = uuid.UUID(str(workspace_id))
        oid = uuid.UUID(str(opportunity_id))
        if self._claims_factory is None:
            return {
                "opportunity_id": str(oid),
                "response_stats": [],
                "overall": {"count": 0, "avg_days": 0, "median_days": 0, "p90_days": 0},
                "negotiation_cadence_days": 0,
                "unavailable": True,
            }
        claims = self._claims_factory(self.s)
        if not hasattr(claims, "response_analytics_for_opportunity"):
            return {
                "opportunity_id": str(oid),
                "response_stats": [],
                "overall": {"count": 0, "avg_days": 0, "median_days": 0, "p90_days": 0},
                "negotiation_cadence_days": 0,
                "unavailable": True,
            }
        return claims.response_analytics_for_opportunity(ws, oid)

    def clause_trends_for_workspace(self, workspace_id) -> dict:
        ws = uuid.UUID(str(workspace_id))
        if self._findings_factory is None:
            return {
                "workspace_id": str(ws),
                "by_category": [],
                "by_pattern": [],
                "loss_reasons": [],
                "unavailable": True,
            }
        store = self._findings_factory(self.s)
        if not hasattr(store, "list_for_workspace"):
            return {
                "workspace_id": str(ws),
                "by_category": [],
                "by_pattern": [],
                "loss_reasons": [],
                "unavailable": True,
            }
        rows = store.list_for_workspace(ws)
        by_category: dict[str, dict] = {}
        by_pattern: dict[str, dict] = {}
        loss_reasons: dict[str, dict] = {}
        for row in rows:
            cat = row.category
            by_category.setdefault(
                cat, {"category": cat, "count": 0, "exposure_minor": 0, "currency": row.currency}
            )
            by_category[cat]["count"] += 1
            if row.amount_exposure:
                by_category[cat]["exposure_minor"] += row.amount_exposure

            pattern = row.pattern_id or "none"
            by_pattern.setdefault(
                pattern,
                {
                    "pattern_id": pattern,
                    "pattern_version": row.pattern_version,
                    "count": 0,
                    "exposure_minor": 0,
                    "currency": row.currency,
                },
            )
            by_pattern[pattern]["count"] += 1
            if row.amount_exposure:
                by_pattern[pattern]["exposure_minor"] += row.amount_exposure

            if row.review_status == "rejected" and row.review_reason:
                loss_reasons.setdefault(
                    row.review_reason,
                    {"reason": row.review_reason, "count": 0, "exposure_minor": 0},
                )
                loss_reasons[row.review_reason]["count"] += 1
                if row.amount_exposure:
                    loss_reasons[row.review_reason]["exposure_minor"] += row.amount_exposure

        return {
            "workspace_id": str(ws),
            "by_category": sorted(by_category.values(), key=lambda x: x["count"], reverse=True),
            "by_pattern": sorted(by_pattern.values(), key=lambda x: x["count"], reverse=True),
            "loss_reasons": sorted(loss_reasons.values(), key=lambda x: x["count"], reverse=True),
        }

    def executive_summary_for_opportunity(
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

        exposure = self.exposure_for_opportunity(
            ws, oid, cost_of_capital_pa=cost_of_capital_pa, currency=currency
        )
        dashboard = self.dashboard_for_opportunity(ws, oid, currency=currency)
        response = self.response_times_for_opportunity(ws, oid)
        forecast = None
        contract_value = getattr(opportunity, "contract_value_minor", None)
        if contract_value is not None:
            forecast = self.forecast_for_opportunity(
                ws,
                oid,
                projected_final_cost_minor=contract_value,
                cost_of_capital_pa=cost_of_capital_pa,
                currency=currency,
            )

        top_risks: list[dict] = []
        if self._findings_factory is not None:
            try:
                store = self._findings_factory(self.s)
                if hasattr(store, "list_for_workspace"):
                    rows = [
                        {
                            "id": str(r.id),
                            "title": r.title,
                            "severity": r.severity,
                            "category": r.category,
                            "amount_exposure": r.amount_exposure,
                            "currency": r.currency,
                            "source_page": r.source_page,
                            "source_quote": r.source_quote,
                            "document_id": str(r.document_id) if r.document_id else None,
                        }
                        for r in store.list_for_workspace(ws)
                        if r.opportunity_id == oid and r.amount_exposure is not None
                    ]
                    top_risks = sorted(
                        rows, key=lambda x: x["amount_exposure"] or 0, reverse=True
                    )[:5]
            except Exception:
                pass

        return {
            "opportunity_id": str(oid),
            "title": getattr(opportunity, "title", None),
            "contract_value_minor": contract_value,
            "currency": getattr(opportunity, "currency", currency),
            "exposure": exposure,
            "dashboard": dashboard,
            "response_times": response,
            "forecast": forecast,
            "top_risks": top_risks,
        }

    def _payment_events(
        self, workspace_id: uuid.UUID, opportunity_id: uuid.UUID
    ) -> list[CtPaymentEvent]:
        return list(
            self.s.scalars(
                select(CtPaymentEvent)
                .where(
                    CtPaymentEvent.workspace_id == workspace_id,
                    CtPaymentEvent.opportunity_id == opportunity_id,
                )
                .order_by(CtPaymentEvent.due_date.asc())
            )
        )

    def payment_schedule_for_opportunity(self, workspace_id, opportunity_id) -> dict:
        ws = uuid.UUID(str(workspace_id))
        oid = uuid.UUID(str(opportunity_id))
        today = date.today()
        events = self._payment_events(ws, oid)
        schedule = []
        collection_actions = []
        release_actions = []
        total_pending = 0
        total_certified = 0
        total_overdue = 0
        for row in events:
            amount = row.amount_minor or 0
            certified = row.certified_amount_minor or 0
            variance = amount - certified
            age_days = (today - row.due_date).days if row.due_date else 0
            entry = {
                "id": str(row.id),
                "kind": row.kind,
                "due_date": row.due_date.isoformat() if row.due_date else None,
                "amount_minor": amount,
                "certified_amount_minor": row.certified_amount_minor,
                "variance_minor": variance,
                "currency": row.currency,
                "status": row.status,
                "age_days": age_days,
                "description": row.description,
            }
            schedule.append(entry)
            if row.status == "pending":
                total_pending += amount
                if age_days > 0:
                    total_overdue += amount
                    collection_actions.append(entry)
            if row.status == "certified" and row.kind in {"retention", "security"}:
                release_actions.append(entry)
            if row.certified_amount_minor is not None:
                total_certified += certified

        return {
            "opportunity_id": str(oid),
            "schedule": schedule,
            "total_pending_minor": total_pending,
            "total_certified_minor": total_certified,
            "total_overdue_minor": total_overdue,
            "collection_actions": collection_actions,
            "release_actions": release_actions,
        }

    def record_payment_event(
        self,
        workspace_id,
        opportunity_id,
        *,
        kind: str,
        due_date: date,
        amount_minor: int,
        certified_amount_minor: int | None = None,
        currency: str = "INR",
        status: str = "pending",
        released_at: datetime | None = None,
        description: str | None = None,
        created_by: uuid.UUID | str,
    ) -> dict:
        ws = uuid.UUID(str(workspace_id))
        oid = uuid.UUID(str(opportunity_id))
        created_by = uuid.UUID(str(created_by))
        if kind not in {"ra", "progress", "retention", "security"}:
            raise ControlTowerError("invalid_payment_kind")
        if status not in {"pending", "certified", "released"}:
            raise ControlTowerError("invalid_payment_status")
        event = CtPaymentEvent(
            workspace_id=ws,
            opportunity_id=oid,
            kind=kind,
            due_date=due_date,
            amount_minor=amount_minor,
            certified_amount_minor=certified_amount_minor,
            currency=currency,
            status=status,
            released_at=released_at,
            description=description,
            created_by=created_by,
        )
        self.s.add(event)
        self.s.commit()
        return self._payment_event_dict(event)

    def _payment_event_dict(self, row: CtPaymentEvent) -> dict:
        return {
            "id": str(row.id),
            "opportunity_id": str(row.opportunity_id),
            "kind": row.kind,
            "due_date": row.due_date.isoformat() if row.due_date else None,
            "amount_minor": row.amount_minor,
            "certified_amount_minor": row.certified_amount_minor,
            "currency": row.currency,
            "status": row.status,
            "released_at": row.released_at.isoformat() if row.released_at else None,
            "description": row.description,
        }

    def economics_for_workspace(
        self,
        workspace_id,
        *,
        cost_of_sales_minor: int | None = None,
        customer_acquisition_cost_minor: int | None = None,
        currency: str = "INR",
    ) -> dict:
        ws = uuid.UUID(str(workspace_id))
        if self._billing_factory is None:
            return {
                "workspace_id": str(ws),
                "currency": currency,
                "unavailable": True,
            }
        billing = self._billing_factory(self.s)
        if not all(
            hasattr(billing, name)
            for name in ("invoices_for_workspace", "project_subscriptions_for_workspace")
        ):
            return {
                "workspace_id": str(ws),
                "currency": currency,
                "unavailable": True,
            }
        invoices = billing.invoices_for_workspace(ws)
        subs = billing.project_subscriptions_for_workspace(ws)
        opps = self._list_opportunities(ws)
        paid_invoices = [i for i in invoices if i.status == "paid" and i.currency == currency]
        total_invoiced = sum(i.amount_minor for i in paid_invoices)

        # Map invoices by opportunity if available (workspace_id is used as proxy here).
        paid_opportunity_ids = set()
        for inv in paid_invoices:
            if inv.workspace_id:
                paid_opportunity_ids.add(str(inv.workspace_id))

        total_opps = len(opps)
        paid_count = len([o for o in opps if str(o.id) in paid_opportunity_ids])

        paid_conversion = _rate(paid_count, total_opps)

        gross_margin = None
        if cost_of_sales_minor is not None and total_invoiced > 0:
            gross_margin = int(round(100 * (total_invoiced - cost_of_sales_minor) / total_invoiced))

        avg_revenue = int(total_invoiced / max(paid_count, 1))
        cac_payback = None
        if customer_acquisition_cost_minor is not None and avg_revenue > 0:
            cac_payback = round(customer_acquisition_cost_minor / avg_revenue, 2)

        # Project retention: paid opportunities with a subscription or more than one invoice.
        sub_opp_ids = {str(s.opportunity_id) for s in subs if s.status == "active"}
        invoices_by_opp: dict[str, int] = {}
        for inv in paid_invoices:
            key = str(inv.workspace_id) if inv.workspace_id else "none"
            invoices_by_opp[key] = invoices_by_opp.get(key, 0) + 1
        retained_count = 0
        for opp_id in paid_opportunity_ids:
            if opp_id in sub_opp_ids or invoices_by_opp.get(opp_id, 0) > 1:
                retained_count += 1
        project_retention = _rate(retained_count, max(paid_count, 1))

        # Expansion revenue: paid invoices beyond the first per opportunity.
        expansion_revenue = 0
        for inv in paid_invoices:
            key = str(inv.workspace_id) if inv.workspace_id else "none"
            if invoices_by_opp.get(key, 0) > 1:
                expansion_revenue += inv.amount_minor

        return {
            "workspace_id": str(ws),
            "currency": currency,
            "total_opportunities": total_opps,
            "paid_opportunities": paid_count,
            "paid_conversion_percent": paid_conversion,
            "total_invoiced_minor": total_invoiced,
            "gross_margin_percent": gross_margin,
            "cost_of_sales_minor": cost_of_sales_minor,
            "customer_acquisition_cost_minor": customer_acquisition_cost_minor,
            "avg_revenue_per_opportunity_minor": avg_revenue,
            "cac_payback_opportunities": cac_payback,
            "project_retention_percent": project_retention,
            "expansion_revenue_minor": expansion_revenue,
            "assumptions": {
                "cost_of_sales_minor": cost_of_sales_minor,
                "customer_acquisition_cost_minor": customer_acquisition_cost_minor,
            },
        }

    def customer_outcomes_for_workspace(
        self,
        workspace_id,
        *,
        hours_per_review_saved: float = 2.0,
        currency: str = "INR",
    ) -> dict:
        ws = uuid.UUID(str(workspace_id))
        result = {"workspace_id": str(ws), "currency": currency}

        risks_priced_count = 0
        risks_priced_value = 0
        if self._findings_factory is not None:
            try:
                store = self._findings_factory(self.s)
                if hasattr(store, "list_for_workspace"):
                    for r in store.list_for_workspace(ws):
                        if r.amount_exposure and r.currency == currency:
                            risks_priced_count += 1
                            risks_priced_value += r.amount_exposure
            except Exception:
                pass
        result["risks_priced_count"] = risks_priced_count
        result["risks_priced_value_minor"] = risks_priced_value

        bad_bids_declined = 0
        bad_bids_value = 0
        omissions_corrected = 0
        omissions_value = 0
        value_notified = 0
        value_certified = 0
        if self._outcomes_factory is not None:
            try:
                outcomes = self._outcomes_factory(self.s)
                if hasattr(outcomes, "bid_outcomes_for_workspace"):
                    for o in outcomes.bid_outcomes_for_workspace(ws):
                        if o["result"] == "declined":
                            bad_bids_declined += 1
                            if o["quoted_value_minor"]:
                                bad_bids_value += o["quoted_value_minor"]
                if hasattr(outcomes, "risk_materializations_for_workspace"):
                    for m in outcomes.risk_materializations_for_workspace(ws):
                        if not m["materialized"] and m["impact_amount_minor"]:
                            omissions_corrected += 1
                            omissions_value += m["impact_amount_minor"]
                if hasattr(outcomes, "claim_recoveries_for_workspace"):
                    for cr in outcomes.claim_recoveries_for_workspace(ws):
                        if cr["currency"] == currency:
                            value_certified += cr["recovered_amount_minor"]
            except Exception:
                pass
        result["bad_bids_declined_count"] = bad_bids_declined
        result["bad_bids_value_minor"] = bad_bids_value
        result["omissions_corrected_count"] = omissions_corrected
        result["omissions_corrected_value_minor"] = omissions_value

        if self._claims_factory is not None:
            try:
                claims = self._claims_factory(self.s)
                if hasattr(claims, "list_claim_summaries"):
                    for opp in self._list_opportunities(ws):
                        for c in claims.list_claim_summaries(ws, opp.id):
                            if c.get("currency") == currency:
                                if c.get("status") in {
                                    "submitted",
                                    "under_review",
                                    "negotiated",
                                    "disputed",
                                }:
                                    value_notified += c.get("claim_amount_minor") or 0
                                if c.get("status") == "settled":
                                    value_certified += c.get("recovered_amount_minor") or 0
                                    value_notified += c.get("claim_amount_minor") or 0
            except Exception:
                pass
        result["value_notified_minor"] = value_notified
        result["value_certified_minor"] = value_certified

        findings_reviewed = 0
        if self._findings_factory is not None:
            try:
                store = self._findings_factory(self.s)
                if hasattr(store, "list_for_workspace"):
                    findings_reviewed = sum(
                        1 for r in store.list_for_workspace(ws) if r.review_status != "proposed"
                    )
            except Exception:
                pass
        result["hours_saved"] = round(findings_reviewed * hours_per_review_saved, 2)
        result["assumptions"] = {"hours_per_review_saved": hours_per_review_saved}

        return result

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


def _rate(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return 0
    return int(round(100 * numerator / denominator))
