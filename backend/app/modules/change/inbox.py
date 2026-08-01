"""Inbox ordering for potential-variation triage (TS-248)."""

from __future__ import annotations

_BAND_ORDER = {"high": 0, "medium": 1, "low": 2}

INBOX_STATUSES = frozenset({"candidate", "triaged"})


def sort_inbox(events: list[dict]) -> list[dict]:
    """High confidence first; within a band, newest first (stable sort)."""
    events.sort(key=lambda e: e.get("created_at") or "", reverse=True)
    events.sort(key=lambda e: _BAND_ORDER.get(e.get("confidence_band", "low"), 3))
    return events
