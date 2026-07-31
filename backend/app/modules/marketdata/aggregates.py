"""Deterministic employer aggregates (TS-199)."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime

MIN_SAMPLE_SIZE = 12


def percentile(values: list[int], pct: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(int(round(pct * (len(ordered) - 1))), len(ordered) - 1)
    return ordered[idx]


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    text = value.strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def compute_aggregates(records: list[dict]) -> dict:
    """Compute employer behaviour aggregates from tender+award records.

    Each record dict expects: bidder_count, value_minor, estimate_minor,
    award_date, tender_end, winner, ocid, classification, buyer_name.
    """
    bidder_counts = [r["bidder_count"] for r in records if r.get("bidder_count") is not None]
    l1_pcts: list[int] = []
    latencies: list[int] = []
    winners: list[str] = []

    for row in records:
        value = row.get("value_minor")
        estimate = row.get("estimate_minor")
        if value is not None and estimate and estimate > 0:
            l1_pcts.append(int(round((value - estimate) * 10000 / estimate)))

        award_dt = _parse_date(row.get("award_date"))
        tender_end = _parse_date(row.get("tender_end"))
        if award_dt and tender_end:
            latencies.append((award_dt - tender_end).days)

        winner = row.get("winner")
        if winner:
            winners.append(str(winner).strip().casefold())

    retender_rate = _retender_rate(records)
    hhi = _winner_hhi(winners)

    return {
        "bidder_count_p50": percentile(bidder_counts, 0.5),
        "bidder_count_p90": percentile(bidder_counts, 0.9),
        "l1_to_estimate_bps_p50": percentile(l1_pcts, 0.5) if l1_pcts else None,
        "award_latency_days_p50": percentile(latencies, 0.5) if latencies else None,
        "retender_rate_bps": retender_rate,
        "winner_concentration_hhi_bps": hhi,
    }


def _retender_rate(records: list[dict]) -> int | None:
    if len(records) < 2:
        return 0
    groups: Counter[tuple[str, str]] = Counter()
    for row in records:
        key = (str(row.get("buyer_name") or ""), str(row.get("classification") or ""))
        groups[key] += 1
    repeated = sum(1 for count in groups.values() if count > 1)
    if not groups:
        return None
    return int(round(repeated * 10000 / len(groups)))


def _winner_hhi(winners: list[str]) -> int | None:
    if not winners:
        return None
    counts = Counter(winners)
    total = sum(counts.values())
    if total == 0:
        return None
    hhi = sum((count / total) ** 2 for count in counts.values())
    return int(round(hhi * 10000))
