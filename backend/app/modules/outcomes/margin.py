"""North-star metric — verified contractor margin protected (TS-234).

Deterministic aggregation over **reviewed** findings and bid outcomes only.
Speculative (unreviewed) value is excluded by construction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_REVIEWED = frozenset({"accepted", "edited"})
_RISK_KINDS = frozenset({"risk_clause", "risk"})


@dataclass
class MarginProtectedSnapshot:
    currency: str = "INR"
    risk_allowances_minor: int = 0
    declined_exposure_avoided_minor: int = 0
    boq_defects_corrected: int = 0
    materialized_impact_minor: int = 0
    total_margin_protected_minor: int = 0
    opportunities_counted: int = 0
    breakdown: dict[str, int] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        return {
            "currency": self.currency,
            "risk_allowances_minor": self.risk_allowances_minor,
            "declined_exposure_avoided_minor": self.declined_exposure_avoided_minor,
            "boq_defects_corrected": self.boq_defects_corrected,
            "materialized_impact_minor": self.materialized_impact_minor,
            "total_margin_protected_minor": self.total_margin_protected_minor,
            "opportunities_counted": self.opportunities_counted,
            "breakdown": dict(self.breakdown),
        }


def compute_margin_protected(
    findings: list,
    *,
    outcomes: list | None = None,
    materializations: list | None = None,
    currency: str = "INR",
) -> MarginProtectedSnapshot:
    """Sum verified margin protected components for a workspace snapshot.

    Only findings with ``review_status`` in ``accepted`` or ``edited`` count.
    ``amount_exposure`` must be a non-negative integer in minor units with an
    explicit currency matching ``currency`` — otherwise the exposure is skipped
    (never invented or approximated).
    """
    outcomes = outcomes or []
    materializations = materializations or []
    declined_opps = {
        str(o.opportunity_id)
        for o in outcomes
        if getattr(o, "result", None) == "declined"
    }

    risk_allowances = 0
    declined_avoided = 0
    boq_corrected = 0
    opp_ids: set[str] = set()

    for row in findings:
        status = getattr(row, "review_status", None) or ""
        if status not in _REVIEWED:
            continue
        opp_id = str(getattr(row, "opportunity_id", ""))
        opp_ids.add(opp_id)
        kind = getattr(row, "kind", "") or ""
        amount = getattr(row, "amount_exposure", None)
        row_currency = (getattr(row, "currency", None) or "").upper()

        if kind == "boq_defect":
            boq_corrected += 1
            continue

        if kind not in _RISK_KINDS and not getattr(row, "pattern_id", None):
            continue
        if amount is None or not isinstance(amount, int) or amount < 0:
            continue
        if row_currency and row_currency != currency.upper():
            continue

        if opp_id in declined_opps:
            declined_avoided += amount
        else:
            risk_allowances += amount

    materialized = 0
    for row in materializations:
        if not getattr(row, "materialized", False):
            continue
        impact = getattr(row, "impact_amount_minor", None)
        row_currency = (getattr(row, "currency", None) or "").upper()
        if impact is None or not isinstance(impact, int) or impact < 0:
            continue
        if row_currency and row_currency != currency.upper():
            continue
        materialized += impact

    total = risk_allowances + declined_avoided + materialized
    return MarginProtectedSnapshot(
        currency=currency.upper(),
        risk_allowances_minor=risk_allowances,
        declined_exposure_avoided_minor=declined_avoided,
        boq_defects_corrected=boq_corrected,
        materialized_impact_minor=materialized,
        total_margin_protected_minor=total,
        opportunities_counted=len(opp_ids),
        breakdown={
            "reviewed_findings": len(
                [f for f in findings if getattr(f, "review_status", "") in _REVIEWED]
            ),
            "declined_opportunities": len(declined_opps),
            "materialized_findings": len(
                [m for m in materializations if getattr(m, "materialized", False)]
            ),
        },
    )
