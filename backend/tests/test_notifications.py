"""Notifications: deadline-digest logic and ConsoleSender."""

from datetime import datetime, timedelta

from app.modules.notifications.digest import deadlines_to_alert, due_in_days, format_digest
from app.modules.notifications.sender import ConsoleSender, Message


def test_due_in_days_counts_calendar_days():
    due = datetime(2026, 7, 30, 18, 0)
    now = datetime(2026, 7, 26, 10, 0)
    assert due_in_days(due, now) == 4


def test_deadlines_to_alert_hits_thresholds():
    now = datetime(2026, 7, 26, 10, 0)
    deadlines = [
        {"kind": "submission", "due_at": now + timedelta(days=7)},
        {"kind": "emd", "due_at": now + timedelta(days=3)},
        {"kind": "prebid", "due_at": now + timedelta(days=5)},
        {"kind": "clarification", "due_at": now + timedelta(days=0)},
        {"kind": "past", "due_at": now - timedelta(days=1)},
    ]
    alerts = deadlines_to_alert(deadlines, now)
    kinds = {a["kind"] for a in alerts}
    assert kinds == {"submission", "emd", "clarification"}
    assert all(a["days"] in {7, 3, 1, 0} for a in alerts)


def test_format_digest_orders_by_urgency():
    now = datetime(2026, 7, 26, 10, 0)
    alerts = [
        {"kind": "submission", "due_at": now + timedelta(days=7), "days": 7},
        {"kind": "emd", "due_at": now + timedelta(days=0), "days": 0},
    ]
    text = format_digest("Bridge", alerts)
    assert "TODAY" in text
    assert text.index("TODAY") < text.index("in 7 day(s)")


def test_console_sender_records_messages():
    sender = ConsoleSender()
    msg = Message(channel="email", to="a@x.com", subject="Tender alert", body="test")
    assert sender.send(msg) is True
    assert sender.outbox == [msg]
