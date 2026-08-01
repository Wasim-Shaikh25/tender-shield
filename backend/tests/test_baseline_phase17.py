"""Unit tests for baseline compare/watchlist helpers (TS-236, TS-237)."""

from app.modules.baseline.compare_award import diff_clauses, diff_findings
from app.modules.baseline.watchlist import obligation_key as watch_obligation_key


def test_diff_clauses_reports_modified_with_verbatim_quotes():
    tender = [
        {
            "clause_ref": "14",
            "text": "Clause 14 — Payment within 30 days of certification.",
            "page_from": 2,
        }
    ]
    award = [
        {
            "clause_ref": "14",
            "text": "Clause 14 — Payment within 60 days of certification.",
            "page_from": 2,
        }
    ]
    delta = diff_clauses(tender, award)
    assert len(delta["changed"]) == 1
    assert "60 days" in delta["changed"][0]["award_quote"]
    assert "30 days" in delta["changed"][0]["tender_quote"]


def test_diff_findings_includes_source_quote_changes():
    tender = [{"category": "ld", "title": "LD cap", "source_quote": "no cap stated"}]
    award = [{"category": "ld", "title": "LD cap", "source_quote": "capped at 10 percent"}]
    delta = diff_findings(tender, award)
    assert delta["changed"][0]["changes"]["source_quote"]["award"] == "capped at 10 percent"


def test_obligation_key_prefers_pattern_id():
    assert watch_obligation_key({"pattern_id": "liquidated_damages_uncapped", "title": "x"}) != (
        watch_obligation_key({"pattern_id": "payment_terms_extended", "title": "x"})
    )
