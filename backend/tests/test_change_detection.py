"""Unit tests for change detection helpers (TS-245, TS-246)."""

from app.modules.change.baseline_diff import candidates_from_diff, normalize_clause
from app.modules.change.signals import classify_signal


def test_normalize_clause_from_snapshot_shape():
    clause = normalize_clause(
        {
            "title": "5",
            "detail": "Clause 5 — Scope. Build to 12m.",
            "source_page": 1,
        }
    )
    assert clause["text"].startswith("Clause 5")
    assert clause["page_from"] == 1


def test_candidates_from_diff_changed_clause():
    diff = {
        "added": [],
        "removed": [],
        "changed": [
            {
                "clause_ref": "5",
                "source_page": 1,
                "tender_quote": "12m depth",
                "award_quote": "15m depth",
            }
        ],
    }
    candidates = candidates_from_diff(diff)
    assert len(candidates) == 1
    assert candidates[0]["confidence_band"] == "high"
    assert "15m" in candidates[0]["source_quote"]


def test_classify_site_instruction_signal():
    result = classify_signal(
        "site_instruction",
        "Site instruction SI-12: proceed with the variation to pile depth.",
    )
    assert result["reason"] == "instruction"
    assert result["notice_type"] == "variation"
    assert result["source_quote"]
