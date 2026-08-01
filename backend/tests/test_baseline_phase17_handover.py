"""Unit tests for handover view filtering (TS-241)."""

from app.modules.baseline.handover_views import filter_handover


def test_site_view_omits_finance_sections():
    pack = {
        "baseline_id": "b1",
        "version": 1,
        "source": "tender",
        "sealed_hash": "abc",
        "sealed_at": "2026-01-01",
        "opportunity": {"title": "Depot"},
        "watchlist_controls": [{"title": "LD cap"}],
        "key_obligations": [{"title": "Payment"}],
        "notice_register": [{"category": "payment"}],
        "exposure_totals": {"total_minor": 1000},
        "finance_notice_windows": [{"category": "payment"}],
    }
    site = filter_handover(pack, "site")
    assert site["view"] == "site"
    assert "watchlist_controls" in site
    assert "exposure_totals" not in site
    assert "finance_notice_windows" not in site


def test_finance_view_keeps_exposure_totals():
    pack = {
        "baseline_id": "b1",
        "version": 1,
        "source": "tender",
        "sealed_hash": "abc",
        "sealed_at": "2026-01-01",
        "opportunity": {"title": "Depot"},
        "exposure_totals": {"total_minor": 5000, "currency": "INR"},
        "finance_notice_windows": [{"category": "payment", "days": 14}],
        "key_obligations": [{"title": "hidden"}],
    }
    finance = filter_handover(pack, "finance")
    assert finance["view"] == "finance"
    assert finance["exposure_totals"]["total_minor"] == 5000
    assert "key_obligations" not in finance
