"""Resolved entitlements for a workspace (Doc §7, R-009). One object answers
every "may they?" question, so a limit cannot be enforced in one module and
forgotten in another — `PLAN_LIMITS` declared seats/quotas that nothing read
until this file existed. Pure over inputs the caller supplies; `seats_used`
in particular comes from `auth` (billing may not query auth's own tables,
CLAUDE.md §2) via the `billing.entitlements` capability's caller.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import UTC, datetime


def as_aware_utc(dt: datetime) -> datetime:
    """SQLite drops tzinfo on read even for a `DateTime(timezone=True)`
    column (Postgres preserves it) — every value ever written here was UTC,
    so a naive value is assumed UTC rather than compared/serialized wrong.
    Matches the same normalization already used for `locked_until`/
    `expires_at` in `auth/service.py`."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


@dataclass(frozen=True)
class Entitlements:
    plan: str
    plan_status: str  # active | past_due | cancelled
    reviews_included: int | None  # None = not metered by count (free/paygo)
    reviews_used: int
    reviews_topup: int
    seats_included: int
    seats_used: int
    watermark_exports: bool
    period_start: datetime
    period_end: datetime

    @property
    def reviews_remaining(self) -> int | None:
        if self.reviews_included is None:
            return None
        return max(self.reviews_included + self.reviews_topup - self.reviews_used, 0)

    @property
    def seats_remaining(self) -> int:
        return max(self.seats_included - self.seats_used, 0)

    @property
    def is_entitled(self) -> bool:
        """past_due within grace keeps full access — never delete or restrict
        on non-payment (specs/modules/billing.md B8). The grace-window check
        itself lives in the caller (workspace.grace_until vs now); this only
        reflects the coarse plan_status."""
        return self.plan_status in ("active", "past_due")


def add_month(dt: datetime) -> datetime:
    """Month-end-safe: 31 Jan -> 28/29 Feb (the target month's actual last
    day), never 3 Mar (R-009 §B.2/A9)."""
    if dt.month == 12:
        return dt.replace(year=dt.year + 1, month=1)
    year, month = dt.year, dt.month + 1
    last_day = calendar.monthrange(year, month)[1]
    return dt.replace(month=month, day=min(dt.day, last_day))


def resolve_entitlements(
    *,
    plan: str,
    plan_status: str,
    seats_included: int,
    reviews_included: int | None,
    reviews_used: int,
    reviews_topup: int,
    seats_used: int,
    period_start: datetime,
    period_end: datetime,
) -> Entitlements:
    return Entitlements(
        plan=plan,
        plan_status=plan_status,
        reviews_included=reviews_included,
        reviews_used=reviews_used,
        reviews_topup=reviews_topup,
        seats_included=seats_included,
        seats_used=seats_used,
        watermark_exports=plan == "free",
        period_start=period_start,
        period_end=period_end,
    )
