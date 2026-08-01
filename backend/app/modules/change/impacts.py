"""Impact-link validation and exposure totals (TS-249).

Deterministic arithmetic in minor units — numbers never from the LLM.
"""

from __future__ import annotations


def normalize_impact_links(payload: dict) -> dict:
    return {
        "boq_src_rows": list(payload.get("boq_src_rows") or []),
        "cost_code_ids": list(payload.get("cost_code_ids") or []),
        "finding_ids": list(payload.get("finding_ids") or []),
        "subcontract_refs": list(payload.get("subcontract_refs") or []),
    }


def validate_impact_links(
    links: dict,
    *,
    valid_cost_code_ids: set[str],
    valid_finding_ids: set[str],
) -> None:
    for code_id in links["cost_code_ids"]:
        if code_id not in valid_cost_code_ids:
            raise ValueError("invalid_cost_code")
    for finding_id in links["finding_ids"]:
        if finding_id not in valid_finding_ids:
            raise ValueError("invalid_finding")


def compute_impact_exposure(
    links: dict,
    findings_by_id: dict[str, object],
) -> dict:
    currency = "INR"
    total = 0
    by_finding: list[dict] = []
    for finding_id in links["finding_ids"]:
        row = findings_by_id.get(finding_id)
        if row is None:
            continue
        amount = getattr(row, "amount_exposure", None) or 0
        currency = getattr(row, "currency", None) or currency
        total += amount
        by_finding.append(
            {
                "finding_id": finding_id,
                "amount_minor": amount,
                "currency": currency,
            }
        )
    return {
        "currency": currency,
        "total_minor": total,
        "by_finding": by_finding,
        "linked_cost_codes": len(links["cost_code_ids"]),
        "linked_boq_rows": len(links["boq_src_rows"]),
        "linked_subcontracts": len(links["subcontract_refs"]),
    }
