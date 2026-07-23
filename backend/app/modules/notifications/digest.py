"""Deadline-digest logic (Doc §11.6/§11.7) — pure. Decides which deadlines
warrant an alert and formats the message; the sender is injected. Alert windows
mirror the countdown wall (≤7 days) plus same-day."""

from __future__ import annotations

from datetime import datetime

ALERT_DAYS = (7, 3, 1, 0)  # days-before thresholds that trigger an alert


def due_in_days(due_at: datetime, now: datetime) -> int:
    return (due_at.date() - now.date()).days


def deadlines_to_alert(deadlines: list[dict], now: datetime) -> list[dict]:
    """`deadlines` are dicts with 'kind', 'due_at' (datetime|None). Returns those
    whose day-count hits an alert threshold and are not already past."""
    out = []
    for d in deadlines:
        due = d.get("due_at")
        if not isinstance(due, datetime):
            continue
        days = due_in_days(due, now)
        if 0 <= days and days in ALERT_DAYS:
            out.append({**d, "days": days})
    return out


def format_digest(opportunity_title: str, alerts: list[dict]) -> str:
    lines = [f"Upcoming deadlines — {opportunity_title}:"]
    for a in sorted(alerts, key=lambda x: x["days"]):
        when = "TODAY" if a["days"] == 0 else f"in {a['days']} day(s)"
        lines.append(f"- {a['kind']}: {a['due_at'].date().isoformat()} ({when})")
    return "\n".join(lines)
