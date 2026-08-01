"""Deterministic notice-deadline engine for change events (TS-251).

Calendar-day arithmetic only — never LLM. Milestone deadlines are read from the
enriched baseline notice register; event-trigger deadlines use the event's
``trigger_date`` plus ``deadline_days``.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta


def _parse_iso_date(value: str | date | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _match_rule(rules: list[dict], notice_type: str | None) -> dict | None:
    if not rules:
        return None
    if notice_type:
        for rule in rules:
            if rule.get("notice_type") == notice_type or rule.get("category") == notice_type:
                return rule
    for rule in rules:
        if rule.get("notice_type") == "variation" or rule.get("category") == "variation":
            return rule
    return rules[0]


def compute_event_trigger_deadline(
    *,
    trigger_date: date,
    deadline_days: int,
) -> dict:
    notice_deadline = trigger_date + timedelta(days=deadline_days)
    return {
        "deadline_unknown": False,
        "notice_deadline": notice_deadline.isoformat(),
        "trigger_date": trigger_date.isoformat(),
        "trigger_event": "event",
    }


def compute_notice_deadline(
    *,
    notice_type: str | None,
    trigger_date: date | None,
    rules: list[dict],
) -> dict:
    """Return deadline payload for a change event using enriched register rules."""
    rule = _match_rule(rules, notice_type)
    if rule is None:
        return {
            "notice_type": notice_type,
            "deadline_unknown": True,
            "deadline_reason": "no_matching_rule",
            "required_content": [],
            "correspondence": None,
        }

    notice_type = rule.get("notice_type") or rule.get("category") or notice_type
    trigger_event = rule.get("trigger_event", "event")
    deadline_days = rule.get("deadline_days") or rule.get("days")
    basis = rule.get("deadline_basis", "calendar")

    payload: dict = {
        "notice_type": notice_type,
        "deadline_days": deadline_days,
        "deadline_basis": basis,
        "trigger_event": trigger_event,
        "required_content": rule.get("required_content") or [],
        "correspondence": rule.get("correspondence"),
        "authorized_representative": rule.get("authorized_representative"),
        "source_quote": rule.get("source_quote"),
        "source_page": rule.get("source_page"),
    }

    if trigger_event == "event":
        effective = trigger_date or _parse_iso_date(rule.get("trigger_date"))
        if not deadline_days:
            payload.update({"deadline_unknown": True, "deadline_reason": "no_days"})
        elif effective is None:
            payload.update({"deadline_unknown": True, "deadline_reason": "no_trigger_date"})
        else:
            payload.update(compute_event_trigger_deadline(
                trigger_date=effective,
                deadline_days=int(deadline_days),
            ))
    else:
        payload["trigger_milestone_kind"] = rule.get("trigger_milestone_kind")
        payload["trigger_date"] = rule.get("trigger_date")
        payload["notice_deadline"] = rule.get("notice_deadline")
        payload["deadline_unknown"] = rule.get("deadline_unknown", True)
        if rule.get("deadline_reason"):
            payload["deadline_reason"] = rule["deadline_reason"]

    return payload
