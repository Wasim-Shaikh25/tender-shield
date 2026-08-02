"""Delay-event critical-path and programme impact analysis (TS-328).

This is a deterministic, dependency-aware impact window calculator, not a full CPM
engine. It reads schedule activities imported by the `integrations.schedule` adapter
and returns activities whose start/finish window overlaps the delay event window,
plus transitive successors based on predecessor links.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta


def _to_date(value: date | str | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(value, fmt).date()  # noqa: DTZ007
            except ValueError:
                continue
    return None


def compute_delay_impact(
    *,
    trigger_date: date,
    delay_days: int,
    activities: list[dict],
) -> dict:
    """Return impacted activities and successor path for a delay event.

    `activities` is a list of dicts with keys:
      - source_native_id (str)
      - name (str)
      - start_date (date|str|None)
      - finish_date (date|str|None)
      - duration_days (int|None)
      - predecessors (list[str]|None) — source_native_id values of predecessors
    """
    window_end = trigger_date + timedelta(days=delay_days)

    by_id: dict[str, dict] = {}
    for act in activities:
        sid = act.get("source_native_id") or act.get("id")
        if not sid:
            continue
        by_id[sid] = {
            **act,
            "start_date": _to_date(act.get("start_date")),
            "finish_date": _to_date(act.get("finish_date")),
        }

    impacted: dict[str, dict] = {}
    for sid, act in by_id.items():
        start = act.get("start_date")
        finish = act.get("finish_date")
        # Overlap if any part of the activity falls inside [trigger_date, window_end].
        in_window = False
        if start and finish:
            in_window = not (finish < trigger_date or start > window_end)
        elif start:
            in_window = trigger_date <= start <= window_end
        elif finish:
            in_window = trigger_date <= finish <= window_end
        if in_window:
            impacted[sid] = act

    # Transitive successors: any activity whose predecessors include an impacted one
    # and whose start is at or after the delay start is considered on the affected path.
    changed = True
    while changed:
        changed = False
        for sid, act in by_id.items():
            if sid in impacted:
                continue
            preds = act.get("predecessors") or []
            start = act.get("start_date")
            if any(p in impacted for p in preds) and start and start >= trigger_date:
                impacted[sid] = act
                changed = True

    # Build a simple path order by start date.
    path = sorted(
        (
            {
                "source_native_id": sid,
                "name": act.get("name", ""),
                "start_date": (
                    act.get("start_date").isoformat() if act.get("start_date") else None
                ),
                "finish_date": (
                    act.get("finish_date").isoformat() if act.get("finish_date") else None
                ),
                "duration_days": act.get("duration_days"),
                "delay_window_days": delay_days,
            }
            for sid, act in impacted.items()
        ),
        key=lambda x: (x["start_date"] or "", x["source_native_id"]),
    )

    return {
        "trigger_date": trigger_date.isoformat(),
        "delay_days": delay_days,
        "window_end": window_end.isoformat(),
        "impacted_count": len(path),
        "impacted_activities": path,
        "note": (
            "Dependency-aware impact window only; does not compute float or total "
            "project delay. No auto entitlement."
        ),
    }
