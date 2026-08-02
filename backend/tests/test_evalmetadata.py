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


def test_extract_metadata_finds_value_and_duration():
    text = (
        "[p1]\n"
        "Estimated cost: INR 1000.00\n"
        "Last date of submission: 25/08/2026 15:00\n"
        "Time for completion: 24 months\n"
    )
    meta = extract_metadata_from_text(text)
    assert meta.value_minor == 1000_00
    assert meta.currency == "INR"
    assert meta.project_duration_months == 24.0


def test_extract_metadata_finds_duration_from_date_range():
    text = "[p1]\nContract period: 01/09/2026 to 01/09/2028\n"
    meta = extract_metadata_from_text(text)
    assert meta.project_duration_months is not None
    assert abs(meta.project_duration_months - 24.0) < 0.1


def test_score_m2_matches_value_and_duration():
    record = {
        "ocid": "ocds-test-3",
        "tender_end": "2026-08-25T15:00:00Z",
        "value_minor": 1000_00,
        "currency": "INR",
        "buyer": {"name": "PWD Division I"},
        "contract_period_start": "2026-09-01T00:00:00Z",
        "contract_period_end": "2028-09-01T00:00:00Z",
    }
    text = (
        "[p1]\n"
        "Name of Employer: PWD Division I\n"
        "Estimated cost: INR 1000.00\n"
        "Last date of submission: 25/08/2026 15:00\n"
        "Time for completion: 24 months\n"
    )
    extracted = extract_metadata_from_text(text, ocid="ocds-test-3")
    result = score_m2(record, extracted)
    assert result.match_rate == 1.0
    fields = {c.field for c in result.comparisons}
    assert "project_duration_months" in fields


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
