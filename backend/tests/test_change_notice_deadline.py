"""Unit tests for notice-deadline engine (TS-251)."""

from datetime import date, timedelta

from app.modules.change.notice_deadline import (
    compute_event_trigger_deadline,
    compute_notice_deadline,
)


def test_event_trigger_adds_calendar_days():
    trigger = date(2026, 8, 1)
    result = compute_event_trigger_deadline(trigger_date=trigger, deadline_days=14)
    assert result["deadline_unknown"] is False
    assert result["notice_deadline"] == (trigger + timedelta(days=14)).isoformat()
    assert result["trigger_date"] == trigger.isoformat()


def test_compute_notice_deadline_uses_event_trigger_date():
    rules = [
        {
            "notice_type": "variation",
            "category": "variation",
            "trigger_event": "event",
            "deadline_days": 14,
            "deadline_basis": "calendar",
            "required_content": ["Written variation notice"],
            "correspondence": {"email": "re@employer.com"},
        }
    ]
    result = compute_notice_deadline(
        notice_type="variation",
        trigger_date=date(2026, 8, 1),
        rules=rules,
    )
    assert result["deadline_unknown"] is False
    assert result["notice_deadline"] == "2026-08-15"
    assert result["required_content"] == ["Written variation notice"]
    assert result["correspondence"]["email"] == "re@employer.com"


def test_compute_notice_deadline_milestone_uses_register_values():
    rules = [
        {
            "notice_type": "claim",
            "trigger_event": "milestone",
            "deadline_days": 14,
            "deadline_unknown": False,
            "notice_deadline": "2026-08-15",
            "trigger_date": "2026-08-01",
            "trigger_milestone_kind": "practical_completion",
            "required_content": ["Written claim notice"],
        }
    ]
    result = compute_notice_deadline(
        notice_type="claim",
        trigger_date=None,
        rules=rules,
    )
    assert result["deadline_unknown"] is False
    assert result["notice_deadline"] == "2026-08-15"
    assert result["trigger_milestone_kind"] == "practical_completion"
