"""Full express report assembly (TS-212)."""

from __future__ import annotations

_SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def build_report(
    *,
    deadlines: list[dict],
    missing_docs: dict,
    findings: list[dict],
    tier: str,
) -> dict:
    findings_sorted = sorted(
        findings,
        key=lambda r: (_SEV_ORDER.get(r.get("severity") or "info", 9), r.get("title") or ""),
    )
    return {
        "tier": tier,
        "variant": "unreviewed",
        "disclaimer": "INDICATIVE — NOT REVIEWED BY A QUALIFIED PROFESSIONAL",
        "deadlines": deadlines,
        "missing_documents": missing_docs,
        "findings": findings_sorted,
        "finding_count": len(findings_sorted),
    }
