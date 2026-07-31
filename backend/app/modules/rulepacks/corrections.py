"""Correction loop — aggregate review outcomes into proposed overlays (TS-218)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

MIN_REVIEWED = 5
FALSE_POSITIVE_RATE_THRESHOLD = 0.5

_RESOLVED = {"accepted", "edited", "rejected", "false_positive"}
_NEGATIVE = {"rejected", "false_positive"}


@dataclass(frozen=True)
class PatternFamilyStats:
    pattern_id: str
    employer_family: str | None
    total: int
    accepted: int
    edited: int
    rejected: int
    false_positive: int

    @property
    def reviewed(self) -> int:
        return self.accepted + self.edited + self.rejected + self.false_positive

    @property
    def negative(self) -> int:
        return self.rejected + self.false_positive

    @property
    def false_positive_rate(self) -> float:
        if self.reviewed == 0:
            return 0.0
        return self.negative / self.reviewed


def aggregate_pattern_stats(
    findings: list,
    *,
    family_for_opportunity: dict[str, str | None],
) -> list[PatternFamilyStats]:
    """Roll up reviewed findings by (pattern_id, employer_family)."""
    buckets: dict[tuple[str, str | None], dict[str, int]] = defaultdict(
        lambda: {
            "total": 0,
            "accepted": 0,
            "edited": 0,
            "rejected": 0,
            "false_positive": 0,
        }
    )
    for row in findings:
        pattern_id = getattr(row, "pattern_id", None)
        if not pattern_id:
            continue
        opp_id = str(getattr(row, "opportunity_id", ""))
        family = family_for_opportunity.get(opp_id)
        status = getattr(row, "review_status", "proposed") or "proposed"
        if status not in _RESOLVED:
            continue
        key = (pattern_id, family)
        buckets[key]["total"] += 1
        if status in buckets[key]:
            buckets[key][status] += 1

    return [
        PatternFamilyStats(
            pattern_id=pattern_id,
            employer_family=family,
            total=counts["total"],
            accepted=counts["accepted"],
            edited=counts["edited"],
            rejected=counts["rejected"],
            false_positive=counts["false_positive"],
        )
        for (pattern_id, family), counts in sorted(buckets.items())
    ]


def suggest_overlay(stats: PatternFamilyStats) -> dict | None:
    """Return a proposed overlay body when thresholds are met."""
    if stats.reviewed < MIN_REVIEWED:
        return None
    if stats.false_positive_rate < FALSE_POSITIVE_RATE_THRESHOLD:
        return None
    scope = stats.employer_family or "workspace"
    return {
        "pattern_id": stats.pattern_id,
        "employer_family": stats.employer_family,
        "scope": scope,
        "action": "review_pattern_for_family",
        "suggested_change": {
            "confidence": "unvalidated",
            "note": (
                f"High rejection rate ({stats.false_positive_rate:.0%}) across "
                f"{stats.reviewed} reviewed findings for {scope}."
            ),
        },
        "disclaimer": "PROPOSED — requires human approval before any pack change",
    }
