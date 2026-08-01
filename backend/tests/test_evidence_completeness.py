"""Unit tests for evidence completeness scoring (TS-255)."""

from app.modules.evidence.completeness import required_types, score_completeness


def test_required_types_for_drawing_revision():
    assert "photograph" in required_types("drawing_revision")
    assert "measurement" in required_types("drawing_revision")


def test_score_completeness_partial():
    result = score_completeness(
        reason="instruction",
        present_types={"photograph"},
    )
    assert result["score"] == 50
    assert "site_instruction" in result["missing_types"]


def test_score_completeness_full():
    result = score_completeness(
        reason="instruction",
        present_types={"site_instruction", "photograph"},
    )
    assert result["score"] == 100
    assert result["missing_types"] == []
