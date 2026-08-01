"""Multi-view handover pack filtering (TS-241)."""

from __future__ import annotations

HANDOVER_VIEWS = frozenset({"site", "planning", "procurement", "finance", "full"})


def _header(pack: dict, view: str) -> dict:
    return {
        "view": view,
        "baseline_id": pack.get("baseline_id"),
        "version": pack.get("version"),
        "source": pack.get("source"),
        "sealed_hash": pack.get("sealed_hash"),
        "sealed_at": pack.get("sealed_at"),
        "opportunity": pack.get("opportunity", {}),
    }


def filter_handover(pack: dict, view: str | None = None) -> dict:
    selected = (view or "full").lower()
    if selected not in HANDOVER_VIEWS:
        selected = "full"
    if selected == "full":
        return {**pack, "view": "full"}

    header = _header(pack, selected)
    if selected == "site":
        return {
            **header,
            "watchlist_controls": pack.get("watchlist_controls", []),
            "key_obligations": pack.get("key_obligations", []),
            "notice_register": pack.get("notice_register", []),
        }
    if selected == "planning":
        return {
            **header,
            "deadline_calendar": pack.get("deadline_calendar", []),
            "notice_register": pack.get("notice_register", []),
            "notice_gaps": pack.get("notice_gaps", []),
        }
    if selected == "procurement":
        return {
            **header,
            "boq_assumptions": pack.get("boq_assumptions", []),
            "cost_codes": pack.get("cost_codes", []),
            "scope_gap_findings": pack.get("scope_gap_findings", []),
        }
    # finance
    return {
        **header,
        "exposure_totals": pack.get("exposure_totals", {}),
        "finance_notice_windows": pack.get("finance_notice_windows", []),
    }
