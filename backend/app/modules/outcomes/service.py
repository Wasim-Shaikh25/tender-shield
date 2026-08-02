"""Outcomes service — bid results and risk materialization (TS-215)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.outcomes.margin import compute_margin_protected
from app.modules.outcomes.models import (
    OcBidOutcome,
    OcClaimRecovery,
    OcRiskMaterialization,
)

VALID_RESULTS = frozenset({"submitted", "won", "lost", "declined", "disqualified"})


class OutcomesError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class OutcomesService:
    def __init__(
        self,
        session: Session,
        *,
        findings_factory: Callable | None = None,
        comparable_awards: Callable | None = None,
        award_prefill: Callable | None = None,
        publish: Callable[[str, dict], int] | None = None,
    ):
        self.s = session
        self._findings_factory = findings_factory
        self._comparable_awards = comparable_awards
        self._award_prefill = award_prefill
        self._publish = publish

    def record_bid_outcome(
        self,
        workspace_id,
        opportunity_id,
        *,
        result: str,
        quoted_value_minor: int | None = None,
        l1_value_minor: int | None = None,
        currency: str = "INR",
        bidder_count: int | None = None,
        decline_reason: str | None = None,
        recorded_by=None,
    ) -> OcBidOutcome:
        if result not in VALID_RESULTS:
            raise OutcomesError("bad_result")
        ws = uuid.UUID(str(workspace_id))
        opp = uuid.UUID(str(opportunity_id))
        row = self.s.scalar(
            select(OcBidOutcome).where(
                OcBidOutcome.workspace_id == ws,
                OcBidOutcome.opportunity_id == opp,
            )
        )
        if row is None:
            row = OcBidOutcome(workspace_id=ws, opportunity_id=opp, result=result)
            self.s.add(row)
        else:
            row.result = result
        row.quoted_value_minor = quoted_value_minor
        row.l1_value_minor = l1_value_minor
        row.currency = currency
        row.bidder_count = bidder_count
        row.decline_reason = decline_reason
        row.recorded_by = uuid.UUID(str(recorded_by)) if recorded_by else None
        self.s.commit()
        self.s.refresh(row)
        if self._publish:
            self._publish(
                "outcome.recorded",
                {
                    "workspace_id": str(ws),
                    "opportunity_id": str(opp),
                    "result": result,
                },
            )
        return row

    def record_claim_outcome(
        self,
        workspace_id,
        opportunity_id,
        *,
        claim_id,
        recovered_amount_minor: int,
        currency: str = "INR",
        recorded_by=None,
    ) -> OcClaimRecovery:
        ws = uuid.UUID(str(workspace_id))
        opp = uuid.UUID(str(opportunity_id))
        cid = uuid.UUID(str(claim_id))
        row = self.s.scalar(
            select(OcClaimRecovery).where(
                OcClaimRecovery.workspace_id == ws,
                OcClaimRecovery.claim_id == cid,
            )
        )
        if row is None:
            row = OcClaimRecovery(
                workspace_id=ws,
                opportunity_id=opp,
                claim_id=cid,
            )
            self.s.add(row)
        if recovered_amount_minor < 0:
            raise OutcomesError("bad_amount")
        row.recovered_amount_minor = recovered_amount_minor
        row.currency = currency
        row.recorded_by = uuid.UUID(str(recorded_by)) if recorded_by else None
        self.s.commit()
        self.s.refresh(row)
        if self._publish:
            self._publish(
                "outcome.claim_recovered",
                {
                    "workspace_id": str(ws),
                    "opportunity_id": str(opp),
                    "claim_id": str(cid),
                    "recovered_amount_minor": recovered_amount_minor,
                    "currency": currency,
                },
            )
        return row

    def for_opportunity(
        self, workspace_id, opportunity_id, *, tender_ref: str | None = None
    ) -> dict:
        ws = uuid.UUID(str(workspace_id))
        opp = uuid.UUID(str(opportunity_id))
        outcome = self.s.scalar(
            select(OcBidOutcome).where(
                OcBidOutcome.workspace_id == ws,
                OcBidOutcome.opportunity_id == opp,
            )
        )
        materializations = list(
            self.s.scalars(
                select(OcRiskMaterialization).where(
                    OcRiskMaterialization.workspace_id == ws,
                    OcRiskMaterialization.opportunity_id == opp,
                )
            )
        )
        prefill = None
        if tender_ref and self._award_prefill is not None:
            try:
                prefill = self._award_prefill(self.s, tender_ref)
            except Exception:
                prefill = None
        elif self._comparable_awards is not None:
            try:
                prefill = self._comparable_awards(self.s, opp)
            except Exception:
                prefill = None
        return {
            "opportunity_id": str(opp),
            "outcome": _outcome_dict(outcome) if outcome else None,
            "materializations": [_materialization_dict(m) for m in materializations],
            "prefill": prefill,
        }

    def mark_materialized(
        self,
        workspace_id,
        finding_id,
        *,
        opportunity_id,
        materialized: bool = True,
        impact_amount_minor: int | None = None,
        currency: str = "INR",
        narrative: str | None = None,
        recorded_by=None,
    ) -> OcRiskMaterialization:
        if self._findings_factory is None:
            raise OutcomesError("findings_unavailable")
        store = self._findings_factory(self.s)
        finding = store.get(workspace_id, finding_id)
        if finding is None:
            raise OutcomesError("finding_not_found")
        if finding.opportunity_id != uuid.UUID(str(opportunity_id)):
            raise OutcomesError("finding_not_found")
        ws = uuid.UUID(str(workspace_id))
        fid = uuid.UUID(str(finding_id))
        opp = uuid.UUID(str(opportunity_id))
        row = self.s.scalar(
            select(OcRiskMaterialization).where(
                OcRiskMaterialization.workspace_id == ws,
                OcRiskMaterialization.finding_id == fid,
            )
        )
        if row is None:
            row = OcRiskMaterialization(
                workspace_id=ws,
                opportunity_id=opp,
                finding_id=fid,
            )
            self.s.add(row)
        row.materialized = materialized
        row.impact_amount_minor = impact_amount_minor
        row.currency = currency
        row.narrative = narrative
        row.recorded_by = uuid.UUID(str(recorded_by)) if recorded_by else None
        self.s.commit()
        self.s.refresh(row)
        if self._publish:
            self._publish(
                "outcome.risk_materialized",
                {
                    "workspace_id": str(ws),
                    "opportunity_id": str(opp),
                    "finding_id": str(fid),
                    "materialized": materialized,
                },
            )
        return row

    def margin_protected(self, workspace_id, *, currency: str = "INR") -> dict:
        if self._findings_factory is None:
            raise OutcomesError("findings_unavailable")
        ws = uuid.UUID(str(workspace_id))
        findings = self._findings_factory(self.s).list_for_workspace(ws)
        outcomes = list(
            self.s.scalars(select(OcBidOutcome).where(OcBidOutcome.workspace_id == ws))
        )
        materializations = list(
            self.s.scalars(
                select(OcRiskMaterialization).where(OcRiskMaterialization.workspace_id == ws)
            )
        )
        recoveries = list(
            self.s.scalars(
                select(OcClaimRecovery).where(OcClaimRecovery.workspace_id == ws)
            )
        )
        return compute_margin_protected(
            findings,
            outcomes=outcomes,
            materializations=materializations,
            claim_recoveries=recoveries,
            currency=currency,
        ).summary()

    def bid_outcomes_for_workspace(self, workspace_id) -> list[dict]:
        ws = uuid.UUID(str(workspace_id))
        rows = list(
            self.s.scalars(select(OcBidOutcome).where(OcBidOutcome.workspace_id == ws))
        )
        return [_outcome_dict(r) for r in rows]

    def risk_materializations_for_workspace(self, workspace_id) -> list[dict]:
        ws = uuid.UUID(str(workspace_id))
        rows = list(
            self.s.scalars(
                select(OcRiskMaterialization).where(OcRiskMaterialization.workspace_id == ws)
            )
        )
        return [_materialization_dict(r) for r in rows]

    def claim_recoveries_for_workspace(self, workspace_id) -> list[dict]:
        ws = uuid.UUID(str(workspace_id))
        rows = list(
            self.s.scalars(select(OcClaimRecovery).where(OcClaimRecovery.workspace_id == ws))
        )
        return [_claim_recovery_dict(r) for r in rows]


def _outcome_dict(row: OcBidOutcome) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "opportunity_id": str(row.opportunity_id),
        "result": row.result,
        "quoted_value_minor": row.quoted_value_minor,
        "l1_value_minor": row.l1_value_minor,
        "currency": row.currency,
        "bidder_count": row.bidder_count,
        "decline_reason": row.decline_reason,
        "recorded_by": str(row.recorded_by) if row.recorded_by else None,
        "recorded_at": row.recorded_at.isoformat() if row.recorded_at else None,
    }


def _materialization_dict(row: OcRiskMaterialization) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "finding_id": str(row.finding_id),
        "materialized": row.materialized,
        "impact_amount_minor": row.impact_amount_minor,
        "currency": row.currency,
        "narrative": row.narrative,
        "recorded_by": str(row.recorded_by) if row.recorded_by else None,
        "recorded_at": row.recorded_at.isoformat() if row.recorded_at else None,
    }


def _claim_recovery_dict(row: OcClaimRecovery) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "opportunity_id": str(row.opportunity_id),
        "claim_id": str(row.claim_id),
        "recovered_amount_minor": row.recovered_amount_minor,
        "currency": row.currency,
        "recorded_by": str(row.recorded_by) if row.recorded_by else None,
        "recorded_at": row.recorded_at.isoformat() if row.recorded_at else None,
    }
