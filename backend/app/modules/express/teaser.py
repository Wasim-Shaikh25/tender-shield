"""Deterministic express teaser assembly (TS-210)."""

from __future__ import annotations

_SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def build_teaser(
    *,
    deadlines: list[dict],
    missing_docs: dict,
    findings: list[dict],
) -> dict:
    severity_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    boq_defects = 0
    boq_value_minor = 0

    for row in findings:
        severity = row.get("severity") or "info"
        category = row.get("category") or "other"
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
        category_counts[category] = category_counts.get(category, 0) + 1
        if row.get("kind") == "boq_defect":
            boq_defects += 1
            exposure = row.get("amount_exposure")
            if isinstance(exposure, int):
                boq_value_minor += exposure

    cited = [
        row
        for row in findings
        if row.get("source_quote") and row.get("source_page") is not None
    ]
    cited.sort(key=lambda r: (_SEV_ORDER.get(r.get("severity") or "info", 9), r.get("title") or ""))
    sample_findings = [
        {
            "severity": row.get("severity"),
            "category": row.get("category"),
            "title": row.get("title"),
            "source_page": row.get("source_page"),
            "source_quote": row.get("source_quote"),
        }
        for row in cited[:2]
    ]

    return {
        "deadlines": deadlines,
        "missing_documents": missing_docs,
        "finding_counts": {
            "by_severity": severity_counts,
            "by_category": category_counts,
        },
        "boq": {
            "defect_count": boq_defects,
            "value_affected_minor": boq_value_minor,
        },
        "sample_findings": sample_findings,
    }
