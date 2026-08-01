"""Unit tests for notice-deadline alert bucketing (TS-252)."""

from datetime import UTC, datetime, timedelta

from app.modules.change.notice_alerts import alert_bucket_for_deadline


def test_alert_bucket_for_notice_deadline():
    today = datetime.now(UTC).date()
    assert alert_bucket_for_deadline(today + timedelta(days=7)) == 7
    assert alert_bucket_for_deadline(today + timedelta(days=3)) == 3
    assert alert_bucket_for_deadline(today + timedelta(days=1)) == 1
    assert alert_bucket_for_deadline(today) == 0
    assert alert_bucket_for_deadline(today - timedelta(days=1)) is None
    assert alert_bucket_for_deadline(today + timedelta(days=14)) is None
