"""Tests for M3 outcome backtest (TS-228)."""

from app.evalbacktest import run_m3_backtest


def _row(ocid: str, award_date: str, value: int, estimate: int, bidders: int):
    return {
        "ocid": ocid,
        "date": award_date,
        "value_minor": value,
        "bidder_count": bidders,
    }, {
        "ocid": ocid,
        "value_minor": estimate,
        "tender_end": "2026-01-01",
        "classification": "45000000",
        "buyer": {"name": "PWD"},
    }


def test_m3_time_split_produces_metrics():
    awards = []
    tenders = []
    for i in range(8):
        award, tender = _row(
            f"ocds-{i}",
            f"2026-0{(i % 6) + 1}-15",
            900_000 + i * 10_000,
            1_000_000,
            3 + (i % 2),
        )
        awards.append(award)
        tenders.append(tender)

    result = run_m3_backtest(tenders, awards, split_ratio=0.5)
    assert result.train_count >= 1
    assert result.test_count >= 1
    assert result.split_date is not None
    assert result.l1_mape is not None


def test_m3_insufficient_awards_returns_notes():
    award, tender = _row("ocds-1", "2026-01-15", 900_000, 1_000_000, 3)
    result = run_m3_backtest([tender], [award])
    assert result.test_count == 0
    assert result.notes
