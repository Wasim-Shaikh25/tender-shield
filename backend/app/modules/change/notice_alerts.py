"""Notice-deadline alert bucketing (TS-252).

Reuses the same 7/3/1/0 day buckets as ingestion deadline alerts.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

ALERT_BUCKETS = (7, 3, 1, 0)


def alert_bucket_for_deadline(notice_deadline: date) -> int | None:
    """Return the alert bucket for a notice deadline date, or None if outside window."""
    today = datetime.now(UTC).date()
    days = (notice_deadline - today).days
    if days < 0:
        return None
    candidates = [bucket for bucket in ALERT_BUCKETS if days <= bucket]
    return min(candidates) if candidates else None
