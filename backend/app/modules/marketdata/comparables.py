"""Comparable-set builder for marketdata (TS-199)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def build_comparable_set(
    anchor: dict,
    pool: list[dict],
    *,
    value_band_pct: float = 0.25,
    lookback_days: int = 730,
    same_division: bool = False,
) -> tuple[list[dict], dict]:
    """Return (awards, filter_dict) for a comparable award set.

    Anchor/pool entries are dicts with keys used by the store query helpers.
    """
    now = datetime.now(UTC).date()
    cutoff = now - timedelta(days=lookback_days)
    anchor_value = anchor.get("value_minor")
    anchor_division = anchor.get("division")
    employer_family = anchor.get("family")

    filter_dict = {
        "employer_family": employer_family,
        "value_band_pct": value_band_pct,
        "lookback_days": lookback_days,
        "same_division": same_division,
        "anchor_value_minor": anchor_value,
        "anchor_classification": anchor.get("classification"),
    }

    selected: list[dict] = []
    for row in pool:
        if row.get("ocid") == anchor.get("ocid"):
            continue
        if employer_family and row.get("family") != employer_family:
            continue
        if same_division and anchor_division and row.get("division") != anchor_division:
            continue
        award_date = _as_date(row.get("award_date"))
        if award_date and award_date < cutoff:
            continue
        row_value = row.get("value_minor")
        if anchor_value and row_value:
            low = int(anchor_value * (1 - value_band_pct))
            high = int(anchor_value * (1 + value_band_pct))
            if not (low <= row_value <= high):
                continue
        selected.append({
            "ocid": row.get("ocid"),
            "winner": row.get("winner"),
            "value_minor": row.get("value_minor"),
            "currency": row.get("currency"),
            "bidder_count": row.get("bidder_count"),
            "award_date": row.get("award_date"),
            "source_url": row.get("source_url"),
        })

    selected.sort(key=lambda r: (r.get("award_date") or "", r.get("ocid") or ""))
    filter_dict["n"] = len(selected)
    return selected, filter_dict


def _as_date(value: str | None):
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None
