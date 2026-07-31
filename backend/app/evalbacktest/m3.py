"""M3 outcome backtest with time-based train/test split (TS-228).

Scores simple employer-scoped baselines against held-out award records.
Split is by award date — never random — to avoid leakage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from statistics import mean
from typing import Any


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    if "T" in text:
        text = text.split("T", 1)[0]
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _group_key(row: dict) -> tuple[str, str]:
    buyer = row.get("buyer_name") or ""
    if not buyer and isinstance(row.get("buyer"), dict):
        buyer = row["buyer"].get("name") or ""
    classification = row.get("classification") or ""
    return (str(buyer).strip().casefold(), str(classification).strip())


def _l1_ratio(value_minor: int | None, estimate_minor: int | None) -> float | None:
    if value_minor is None or not estimate_minor:
        return None
    return (value_minor - estimate_minor) / estimate_minor


def _award_latency_days(award_date: str | None, tender_end: str | None) -> int | None:
    award_dt = _parse_date(award_date)
    end_dt = _parse_date(tender_end)
    if award_dt and end_dt:
        return (award_dt - end_dt).days
    return None


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _mape(actual: list[float], predicted: list[float]) -> float | None:
    pairs = [(a, p) for a, p in zip(actual, predicted, strict=True) if a != 0]
    if not pairs:
        return None
    return mean(abs((a - p) / a) for a, p in pairs)


def _mae(actual: list[float], predicted: list[float]) -> float | None:
    pairs = list(zip(actual, predicted, strict=True))
    if not pairs:
        return None
    return mean(abs(a - p) for a, p in pairs)


def _auc(scores: list[float], labels: list[int]) -> float | None:
    """Rank-based AUC for binary labels (no sklearn dependency)."""
    if not scores or len(set(labels)) < 2:
        return None
    pairs = sorted(zip(scores, labels, strict=True), key=lambda x: x[0])
    n_pos = sum(labels)
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        return None
    rank_sum = 0.0
    for i, (_score, label) in enumerate(pairs, start=1):
        if label:
            rank_sum += i
    return (rank_sum - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


@dataclass
class M3Result:
    split_date: str | None = None
    train_count: int = 0
    test_count: int = 0
    l1_mape: float | None = None
    bidder_count_mae: float | None = None
    award_latency_mae: float | None = None
    retender_auc: float | None = None
    notes: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "split_date": self.split_date,
            "train_count": self.train_count,
            "test_count": self.test_count,
            "l1_mape": self.l1_mape,
            "bidder_count_mae": self.bidder_count_mae,
            "award_latency_mae": self.award_latency_mae,
            "retender_auc": self.retender_auc,
            "notes": self.notes,
        }


def _join_records(tenders: list[dict], awards: list[dict]) -> list[dict]:
    tender_by_ocid = {t.get("ocid"): t for t in tenders if t.get("ocid")}
    rows: list[dict] = []
    for award in awards:
        ocid = award.get("ocid")
        if not ocid:
            continue
        tender = tender_by_ocid.get(ocid, {})
        buyer_name = ""
        buyer = tender.get("buyer")
        if isinstance(buyer, dict):
            buyer_name = buyer.get("name") or ""
        rows.append(
            {
                "ocid": ocid,
                "award_date": award.get("date"),
                "value_minor": award.get("value_minor"),
                "estimate_minor": tender.get("value_minor"),
                "tender_end": tender.get("tender_end"),
                "bidder_count": award.get("bidder_count"),
                "buyer_name": buyer_name,
                "classification": tender.get("classification") or "",
                "buyer": buyer,
            }
        )
    return rows


def run_m3_backtest(
    tenders: list[dict],
    awards: list[dict],
    *,
    split_ratio: float = 0.7,
) -> M3Result:
    """Time-split backtest on award records joined to tender metadata."""
    rows = _join_records(tenders, awards)
    dated = [r for r in rows if _parse_date(r.get("award_date"))]
    dated.sort(key=lambda r: _parse_date(r["award_date"]) or date.min)
    if len(dated) < 4:
        return M3Result(notes=["insufficient dated awards for time split (need >= 4)"])

    split_idx = max(1, min(len(dated) - 1, int(len(dated) * split_ratio)))
    train = dated[:split_idx]
    test = dated[split_idx:]
    split_date = train[-1].get("award_date")

    group_l1: dict[tuple[str, str], list[float]] = {}
    group_bidders: dict[tuple[str, str], list[float]] = {}
    group_latency: dict[tuple[str, str], list[float]] = {}
    group_counts: dict[tuple[str, str], int] = {}
    global_l1: list[float] = []
    global_bidders: list[float] = []
    global_latency: list[float] = []

    for row in train:
        key = _group_key(row)
        group_counts[key] = group_counts.get(key, 0) + 1
        ratio = _l1_ratio(row.get("value_minor"), row.get("estimate_minor"))
        if ratio is not None:
            group_l1.setdefault(key, []).append(ratio)
            global_l1.append(ratio)
        bidders = row.get("bidder_count")
        if bidders is not None:
            group_bidders.setdefault(key, []).append(float(bidders))
            global_bidders.append(float(bidders))
        latency = _award_latency_days(row.get("award_date"), row.get("tender_end"))
        if latency is not None:
            group_latency.setdefault(key, []).append(float(latency))
            global_latency.append(float(latency))

    def _predict(key: tuple[str, str], store: dict, global_vals: list[float]) -> float | None:
        vals = store.get(key) or global_vals
        return _median(vals)

    l1_actual: list[float] = []
    l1_pred: list[float] = []
    bidder_actual: list[float] = []
    bidder_pred: list[float] = []
    latency_actual: list[float] = []
    latency_pred: list[float] = []
    retender_scores: list[float] = []
    retender_labels: list[int] = []

    train_keys = set(_group_key(r) for r in train)
    for row in test:
        key = _group_key(row)
        ratio = _l1_ratio(row.get("value_minor"), row.get("estimate_minor"))
        pred_l1 = _predict(key, group_l1, global_l1)
        if ratio is not None and pred_l1 is not None:
            l1_actual.append(ratio)
            l1_pred.append(pred_l1)

        bidders = row.get("bidder_count")
        pred_bidders = _predict(key, group_bidders, global_bidders)
        if bidders is not None and pred_bidders is not None:
            bidder_actual.append(float(bidders))
            bidder_pred.append(pred_bidders)

        latency = _award_latency_days(row.get("award_date"), row.get("tender_end"))
        pred_latency = _predict(key, group_latency, global_latency)
        if latency is not None and pred_latency is not None:
            latency_actual.append(float(latency))
            latency_pred.append(pred_latency)

        repeat_train = group_counts.get(key, 0) > 1
        retender_scores.append(1.0 if repeat_train else 0.0)
        retender_labels.append(1 if key in train_keys and group_counts.get(key, 0) > 0 else 0)

    return M3Result(
        split_date=split_date,
        train_count=len(train),
        test_count=len(test),
        l1_mape=_mape(l1_actual, l1_pred),
        bidder_count_mae=_mae(bidder_actual, bidder_pred),
        award_latency_mae=_mae(latency_actual, latency_pred),
        retender_auc=_auc(retender_scores, retender_labels),
    )
