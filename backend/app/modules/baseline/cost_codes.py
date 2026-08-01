"""Cost-code helpers (TS-240).

Deterministic totals in minor units — numbers never from the LLM.
"""

from __future__ import annotations

from datetime import UTC, datetime

_BOQ_KINDS = frozenset({"boq_defect"})
_SCOPE_CATEGORIES = frozenset({"scope", "scope_gap", "arith", "duplicate"})


def code_dict(row, *, mappings: list[dict] | None = None) -> dict:
    return {
        "id": str(row.id),
        "parent_id": str(row.parent_id) if row.parent_id else None,
        "code": row.code,
        "label": row.label,
        "variation_category": row.variation_category,
        "locked_at": row.locked_at.isoformat() if row.locked_at else None,
        "mappings": mappings or [],
    }


def mapping_dict(row) -> dict:
    return {
        "id": str(row.id),
        "cost_code_id": str(row.cost_code_id),
        "boq_src_row": row.boq_src_row,
        "finding_id": str(row.finding_id) if row.finding_id else None,
        "description_match": row.description_match,
    }


def build_tree(codes: list[dict]) -> list[dict]:
    by_parent: dict[str | None, list[dict]] = {}
    for entry in codes:
        by_parent.setdefault(entry.get("parent_id"), []).append(entry)

    def attach(parent_id: str | None) -> list[dict]:
        nodes = []
        for entry in sorted(by_parent.get(parent_id, []), key=lambda c: c["code"]):
            child = dict(entry)
            child["children"] = attach(entry["id"])
            nodes.append(child)
        return nodes

    return attach(None)


def snapshot_cost_codes(codes: list[dict], mappings: list[dict]) -> list[dict]:
    mapping_index: dict[str, list[dict]] = {}
    for mapping in mappings:
        mapping_index.setdefault(mapping["cost_code_id"], []).append(mapping)
    out = []
    for code in codes:
        row = dict(code)
        row["mappings"] = mapping_index.get(code["id"], [])
        out.append(row)
    return out


def compute_exposure_totals(
    findings: list[dict],
    mappings: list[dict],
) -> dict:
    by_finding = {f["id"]: f for f in findings if f.get("id")}
    by_code: dict[str, dict] = {}
    currency = "INR"
    for mapping in mappings:
        finding = by_finding.get(mapping.get("finding_id") or "")
        if finding is None:
            continue
        amount = finding.get("amount_exposure")
        if amount is None:
            continue
        currency = finding.get("currency") or currency
        bucket = by_code.setdefault(
            mapping["cost_code_id"],
            {"cost_code_id": mapping["cost_code_id"], "amount_minor": 0, "currency": currency},
        )
        bucket["amount_minor"] += int(amount)
        bucket["currency"] = finding.get("currency") or bucket["currency"]

    total_minor = sum(row["amount_minor"] for row in by_code.values())
    return {
        "currency": currency,
        "total_minor": total_minor,
        "by_cost_code": sorted(by_code.values(), key=lambda r: r["cost_code_id"]),
    }


def boq_assumption_findings(findings: list[dict]) -> list[dict]:
    return [
        f
        for f in findings
        if f.get("kind") in _BOQ_KINDS or f.get("category") in _SCOPE_CATEGORIES
    ]


def scope_gap_findings(findings: list[dict]) -> list[dict]:
    return [f for f in findings if f.get("category") in {"scope", "scope_gap"}]


def finance_notice_windows(notice_rules: list[dict]) -> list[dict]:
    keys = {"payment", "ld", "liquidated_damages", "retention", "defect"}
    return [r for r in notice_rules if r.get("notice_type") in keys or r.get("category") in keys]


def lock_timestamp() -> datetime:
    return datetime.now(UTC)
