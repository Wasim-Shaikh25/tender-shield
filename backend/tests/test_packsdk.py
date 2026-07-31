"""Tests for the pack SDK (TS-220).

Covers both directions for every check: a well-formed pack must pass cleanly,
and a broken one must be caught with a specific, actionable message — a
validator that never fails is exactly as useless as one that always does.
Also proves the acceptance gate directly: the checked-in example pack
(`evals/pack-sdk-example/`) validates and tests clean, and the real product
pack (`rulepacks/in-works/`) does too.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from app.packsdk import run_pack_tests, validate_pack

REPO_ROOT = Path(__file__).resolve().parents[2]
IN_WORKS = REPO_ROOT / "rulepacks" / "in-works"
EXAMPLE_PACK = REPO_ROOT / "evals" / "pack-sdk-example"


# --------------------------------------------------------- the real packs


def test_example_pack_validates_cleanly():
    """The acceptance gate: a third-party-authored pack validates end to end."""
    report = validate_pack(EXAMPLE_PACK)
    assert report.ok, report.to_dict()
    assert report.schema_errors == {}
    assert report.errors == []


def test_example_pack_tests_pass():
    result = run_pack_tests(EXAMPLE_PACK)
    assert result.passed, result.to_dict()
    assert len(result.cases) == 1


def test_in_works_pack_validates_cleanly():
    """The product's own pack must pass its own validator — if it didn't,
    the validator would be stricter than the product it's meant to serve."""
    report = validate_pack(IN_WORKS)
    assert report.ok, report.to_dict()


# ------------------------------------------------------------------ fixtures


def _write_minimal_pack(root: Path, **overrides) -> Path:
    pack_dir = root / "broken-pack"
    (pack_dir / "risk_patterns").mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        yaml.dump(
            {
                "id": "broken-pack",
                "version": "1.0",
                "jurisdiction": "IN",
                "effective_from": "2026-01-01",
                "sources": ["test fixture"],
            }
        )
    )
    pattern = {
        "id": "p1",
        "category": "test",
        "title": "Test pattern",
        "confidence": "unvalidated",
        "source": "test fixture",
        "severity_rule": "medium",
        "anchor_queries": ["test"],
        "judgment_prompt": "test",
    }
    pattern.update(overrides)
    (pack_dir / "risk_patterns" / "p1.yaml").write_text(yaml.dump(pattern))
    return pack_dir


# --------------------------------------------------------------- validate()


def test_missing_source_is_a_validation_error(tmp_path):
    pack_dir = _write_minimal_pack(tmp_path, source="")
    report = validate_pack(pack_dir)
    # An empty source fails Pydantic's min_length=1 -> a schema error, not a
    # lint issue — the loader itself rejects it, which is the stricter and
    # correct outcome.
    assert not report.ok
    assert report.schema_errors


def test_malformed_severity_rule_is_caught(tmp_path):
    pack_dir = _write_minimal_pack(tmp_path, severity_rule="high if )( else low")
    report = validate_pack(pack_dir)
    assert not report.ok
    assert any(i.code == "bad_severity_rule" for i in report.errors)


def test_id_mismatch_is_a_warning_not_an_error(tmp_path):
    pack_dir = tmp_path / "broken-pack"
    (pack_dir / "risk_patterns").mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        yaml.dump(
            {
                "id": "some-other-id",
                "version": "1.0",
                "jurisdiction": "IN",
                "effective_from": "2026-01-01",
                "sources": ["x"],
            }
        )
    )
    report = validate_pack(pack_dir)
    assert report.ok  # a warning alone does not fail validation
    assert any(i.code == "id_mismatch" for i in report.warnings)


def test_duplicate_pattern_id_across_files_is_an_error(tmp_path):
    pack_dir = _write_minimal_pack(tmp_path)
    pattern2 = yaml.safe_load((pack_dir / "risk_patterns" / "p1.yaml").read_text())
    (pack_dir / "risk_patterns" / "p1_duplicate.yaml").write_text(yaml.dump(pattern2))
    report = validate_pack(pack_dir)
    assert not report.ok
    assert any(i.code == "duplicate_id" for i in report.errors)


def test_duplicate_checklist_item_key_is_an_error(tmp_path):
    pack_dir = _write_minimal_pack(tmp_path)
    (pack_dir / "boq" / "trade_checklists").mkdir(parents=True)
    checklist = {
        "id": "c1",
        "trade": "civil",
        "confidence": "unvalidated",
        "source": "test",
        "items": [
            {
                "key": "dup",
                "label": "A",
                "severity": "low",
                "triggers": ["x"],
                "boq_patterns": ["x"],
            },
            {
                "key": "dup",
                "label": "B",
                "severity": "low",
                "triggers": ["y"],
                "boq_patterns": ["y"],
            },
        ],
    }
    (pack_dir / "boq" / "trade_checklists" / "c1.yaml").write_text(yaml.dump(checklist))
    report = validate_pack(pack_dir)
    assert not report.ok
    assert any(i.code == "duplicate_item_key" for i in report.errors)


def test_unregistered_formula_is_a_warning(tmp_path):
    pack_dir = _write_minimal_pack(
        tmp_path,
        price_impact={
            "basis": "percent_of_contract_value",
            "formula": "not_a_real_formula",
            "inputs": ["x"],
        },
    )
    report = validate_pack(pack_dir)
    assert report.ok  # unregistered formula is a warning, not a hard failure
    assert any(i.code == "unregistered_formula" for i in report.warnings)


def test_pack_with_zero_patterns_warns_but_does_not_fail(tmp_path):
    pack_dir = tmp_path / "empty-pack"
    pack_dir.mkdir()
    (pack_dir / "pack.yaml").write_text(
        yaml.dump(
            {
                "id": "empty-pack",
                "version": "1.0",
                "jurisdiction": "IN",
                "effective_from": "2026-01-01",
                "sources": ["x"],
            }
        )
    )
    report = validate_pack(pack_dir)
    assert report.ok
    assert any(i.code == "no_patterns" for i in report.warnings)


# ------------------------------------------------------------- run_pack_tests


def test_pack_with_no_tests_directory_reports_zero_cases(tmp_path):
    pack_dir = _write_minimal_pack(tmp_path)
    result = run_pack_tests(pack_dir)
    assert result.cases == []
    assert result.passed is False  # zero cases is not a pass — nothing was proven


def test_a_missing_expected_gap_fails_the_case(tmp_path):
    pack_dir = tmp_path / "pack"
    (pack_dir / "risk_patterns").mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        yaml.dump(
            {
                "id": "pack", "version": "1.0", "jurisdiction": "IN",
                "effective_from": "2026-01-01", "sources": ["x"],
            }
        )
    )
    (pack_dir / "boq" / "trade_checklists").mkdir(parents=True)
    checklist = {
        "id": "c1", "trade": "civil", "confidence": "unvalidated", "source": "x",
        "items": [
            {"key": "k1", "label": "L1", "severity": "low", "triggers": ["trig"],
             "boq_patterns": ["pat"]},
        ],
    }
    (pack_dir / "boq" / "trade_checklists" / "c1.yaml").write_text(yaml.dump(checklist))
    (pack_dir / "tests" / "scope_gaps").mkdir(parents=True)
    case = {
        "checklist_id": "c1",
        "spec_text": "[p1]\ntrig present here",
        "boq_rows": [
            {"src_row": 1, "item_code": "", "description": "unrelated item",
             "unit_raw": "nos", "qty": 1, "rate": 10, "amount": 10},
        ],
        # deliberately wrong expectation: claims the gap does NOT fire, but it does
        "expect_gap_keys": [],
        "expect_no_gap_keys": ["k1"],
    }
    (pack_dir / "tests" / "scope_gaps" / "case1.yaml").write_text(yaml.dump(case))

    result = run_pack_tests(pack_dir)
    assert result.passed is False
    assert result.cases[0].unexpected_gaps == ["k1"]


def test_unknown_checklist_id_in_a_case_is_a_reported_error(tmp_path):
    pack_dir = _write_minimal_pack(tmp_path)
    (pack_dir / "tests" / "scope_gaps").mkdir(parents=True)
    (pack_dir / "tests" / "scope_gaps" / "bad.yaml").write_text(
        yaml.dump({"checklist_id": "does-not-exist", "boq_rows": []})
    )
    result = run_pack_tests(pack_dir)
    assert result.cases[0].passed is False
    assert "unknown checklist_id" in result.cases[0].error


def test_boq_rows_missing_required_columns_is_reported(tmp_path):
    pack_dir = tmp_path / "pack"
    (pack_dir / "risk_patterns").mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        yaml.dump(
            {"id": "pack", "version": "1.0", "jurisdiction": "IN",
             "effective_from": "2026-01-01", "sources": ["x"]}
        )
    )
    (pack_dir / "boq" / "trade_checklists").mkdir(parents=True)
    checklist = {
        "id": "c1", "trade": "civil", "confidence": "unvalidated", "source": "x",
        "items": [{"key": "k1", "label": "L1", "severity": "low", "triggers": ["t"],
                    "boq_patterns": ["p"]}],
    }
    (pack_dir / "boq" / "trade_checklists" / "c1.yaml").write_text(yaml.dump(checklist))
    (pack_dir / "tests" / "scope_gaps").mkdir(parents=True)
    (pack_dir / "tests" / "scope_gaps" / "bad.yaml").write_text(
        yaml.dump({"checklist_id": "c1", "boq_rows": [{"description": "x"}]})
    )
    result = run_pack_tests(pack_dir)
    assert result.cases[0].passed is False
    assert "missing columns" in result.cases[0].error


def test_a_malformed_case_file_does_not_crash_the_run(tmp_path):
    pack_dir = _write_minimal_pack(tmp_path)
    (pack_dir / "tests" / "scope_gaps").mkdir(parents=True)
    (pack_dir / "tests" / "scope_gaps" / "bad.yaml").write_text("{not: valid: yaml: [")
    result = run_pack_tests(pack_dir)
    assert result.cases[0].passed is False
    assert result.cases[0].error is not None
