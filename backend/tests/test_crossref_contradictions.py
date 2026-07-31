"""Deterministic fact extraction + contradiction resolution (TS-217,
Strategy Doc §C.5). No LLM, no DB — pure regex/logic, unit-tested directly."""

from app.modules.crossref import contradictions as contradictions_mod
from app.modules.crossref.contradictions import (
    DEFAULT_PRECEDENCE,
    find_contradictions,
    resolve_governing,
)
from app.modules.crossref.facts import CanonicalFact, extract_facts


def _clause(id_, document_id, document_kind, text, page=1):
    return {
        "id": id_,
        "document_id": document_id,
        "document_kind": document_kind,
        "text": text,
        "page_from": page,
    }


# ---------------------------------------------------------------------------
# facts.py — one extractor per canonical fact type
# ---------------------------------------------------------------------------


def test_extract_bid_validity_days():
    text = "The bid shall remain valid for 90 (ninety) days from the date of opening."
    facts = extract_facts([_clause("c1", "d1", "nit", text)])
    assert [(f.fact_type, f.value) for f in facts] == [("bid_validity_days", 90)]
    assert "90" in facts[0].source_quote


def test_extract_emd_percent_and_amount_are_distinct_fact_types():
    percent_text = (
        "The bidder shall deposit an Earnest Money Deposit equal to 2% of the estimated cost."
    )
    amount_text = "Earnest Money Deposit of Rs. 50,000 shall accompany the bid."
    percent = extract_facts([_clause("c1", "d1", "nit", percent_text)])
    amount = extract_facts([_clause("c2", "d1", "nit", amount_text)])
    assert [(f.fact_type, f.value) for f in percent] == [("emd_percent", 2.0)]
    # Minor units (paise), never float (CLAUDE.md §4).
    assert [(f.fact_type, f.value) for f in amount] == [("emd_amount_minor", 5_000_000)]


def test_extract_ld_rate_percent_with_period():
    text = "Liquidated damages shall be levied at 0.5% per week of delay."
    facts = extract_facts([_clause("c1", "d1", "gcc", text)])
    assert [(f.fact_type, f.value) for f in facts] == [("ld_rate_percent", "0.5%/week")]


def test_extract_dlp_months():
    text = "The Defect Liability Period shall be 12 months from the date of virtual completion."
    facts = extract_facts([_clause("c1", "d1", "gcc", text)])
    assert [(f.fact_type, f.value) for f in facts] == [("dlp_months", 12)]


def test_extract_retention_percent():
    text = "Retention money shall be deducted at 5% of the gross value of work done."
    facts = extract_facts([_clause("c1", "d1", "gcc", text)])
    assert [(f.fact_type, f.value) for f in facts] == [("retention_percent", 5.0)]


def test_extract_submission_datetime():
    text = "Bids shall be submitted on or before 15-08-2026 up to 15:00 hrs."
    facts = extract_facts([_clause("c1", "d1", "nit", text)])
    assert [(f.fact_type, f.value) for f in facts] == [("submission_datetime", "2026-08-15T15:00")]


def test_invalid_calendar_date_is_skipped_not_guessed():
    text = "Bids shall be submitted on or before 31-02-2026."
    assert extract_facts([_clause("c1", "d1", "nit", text)]) == []


def test_no_match_returns_no_facts():
    text = "This clause mentions nothing quantitative."
    assert extract_facts([_clause("c1", "d1", "nit", text)]) == []


def test_source_quote_is_always_a_substring_of_the_clause_text():
    text = "The bid shall remain valid for 90 (ninety) days from the date of opening."
    facts = extract_facts([_clause("c1", "d1", "nit", text)])
    assert facts[0].source_quote in text


# ---------------------------------------------------------------------------
# contradictions.py — grouping, precedence, verification gate
# ---------------------------------------------------------------------------


_VALID_90 = "The bid shall remain valid for 90 days from the date of opening."
_VALID_120 = "The bid shall remain valid for 120 days from the date of opening."


def test_no_contradiction_when_all_documents_agree():
    clauses = [
        _clause("c1", "d1", "gcc", _VALID_90),
        _clause("c2", "d2", "addendum", _VALID_90),
    ]
    assert find_contradictions(clauses) == []


def test_contradiction_detected_and_addendum_governs_over_gcc():
    clauses = [
        _clause("c1", "d1", "gcc", _VALID_90),
        _clause("c2", "d2", "addendum", _VALID_120),
    ]
    result = find_contradictions(clauses)
    assert len(result) == 1
    c = result[0]
    assert c.fact_type == "bid_validity_days"
    assert {f.value for f in c.instances} == {90, 120}
    assert c.governing is not None
    assert c.governing.value == 120
    assert c.governing.document_kind == "addendum"
    assert "addendum" in c.governing_reason


def test_ambiguous_when_conflicting_instances_tie_on_precedence():
    dlp_12 = "The Defect Liability Period shall be 12 months from completion."
    dlp_24 = "The Defect Liability Period shall be 24 months from completion."
    clauses = [
        _clause("c1", "d1", "gcc", dlp_12),
        _clause("c2", "d2", "gcc", dlp_24),
    ]
    result = find_contradictions(clauses)
    assert len(result) == 1
    assert result[0].governing is None
    assert "ambiguous" in result[0].governing_reason


def test_employer_family_override_can_flip_governing_instance():
    retention_5 = "Retention money shall be deducted at 5% of the gross value of work done."
    retention_10 = "Retention money shall be deducted at 10% of the gross value of work done."
    clauses = [
        _clause("c1", "d1", "gcc", retention_5),
        _clause("c2", "d2", "scc", retention_10),
    ]
    default_result = find_contradictions(clauses, precedence=DEFAULT_PRECEDENCE)
    assert default_result[0].governing.value == 10.0  # scc outranks gcc by default

    flipped = find_contradictions(clauses, precedence=("gcc", "scc", "addendum", "nit"))
    assert flipped[0].governing.value == 5.0


def test_unverifiable_extracted_fact_is_dropped_before_grouping(monkeypatch):
    # Simulate extraction noise: a "fact" whose quote does not actually occur
    # in its own clause's text must never be allowed to participate in a
    # contradiction (Strategy §C.5's explicit false-positive guard).
    fake_facts = [
        CanonicalFact(
            fact_type="bid_validity_days",
            value=90,
            unit="bid_validity_days",
            document_id="d1",
            document_kind="gcc",
            clause_id="c1",
            source_page=1,
            source_quote="a quote that is not actually in the clause",
        ),
        CanonicalFact(
            fact_type="bid_validity_days",
            value=120,
            unit="bid_validity_days",
            document_id="d2",
            document_kind="addendum",
            clause_id="c2",
            source_page=1,
            source_quote="shall remain valid for 120 days",
        ),
    ]
    monkeypatch.setattr(contradictions_mod, "extract_facts", lambda clauses: fake_facts)
    clauses = [
        _clause("c1", "d1", "gcc", "totally unrelated clause text"),
        _clause("c2", "d2", "addendum", "The bid shall remain valid for 120 days from opening."),
    ]
    # Only the addendum instance survives verification — with a single
    # verified instance there is nothing left to disagree with.
    assert contradictions_mod.find_contradictions(clauses) == []


def test_unknown_document_kind_ranks_lowest():
    instances = (
        CanonicalFact("dlp_months", 12, "dlp_months", "d1", "cover_letter", "c1", 1, "12 months"),
        CanonicalFact("dlp_months", 24, "dlp_months", "d2", "gcc", "c2", 1, "24 months"),
    )
    governing, reason = resolve_governing(instances, DEFAULT_PRECEDENCE)
    assert governing.document_kind == "gcc"
    assert "gcc" in reason
