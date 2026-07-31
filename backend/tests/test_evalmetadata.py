"""Tests for M2 portal-metadata agreement (TS-227)."""


from app.evalmetadata import extract_metadata_from_text, score_m2


def test_extract_metadata_finds_submission_deadline():
    text = "[p1]\nLast date of submission: 25/08/2026 15:00"
    meta = extract_metadata_from_text(text)
    assert meta.submission_deadline is not None
    assert meta.submission_deadline.day == 25


def test_score_m2_matches_portal_deadline():
    record = {
        "ocid": "ocds-test-1",
        "tender_end": "2026-08-25T15:00:00Z",
    }
    extracted = extract_metadata_from_text(
        "[p1]\nLast date of submission: 25/08/2026 15:00",
        ocid="ocds-test-1",
    )
    result = score_m2(record, extracted)
    assert result.graded_fields >= 2
    assert result.match_rate == 1.0


def test_score_m2_triages_extraction_miss():
    record = {
        "ocid": "ocds-test-2",
        "tender_end": "2026-08-25T15:00:00Z",
        "value_minor": 100_00,
        "currency": "INR",
    }
    extracted = extract_metadata_from_text("No dates or values here.", ocid="ocds-test-2")
    result = score_m2(record, extracted)
    assert result.triage_counts.get("extraction_miss", 0) >= 1
    assert result.match_rate is not None and result.match_rate < 1.0
