"""M5 human gold set scorer tests (TS-233)."""

from __future__ import annotations

from pathlib import Path

import yaml

from app.evalgold import GoldCase, load_expected, load_manifest, score_case, score_m5
from app.evalgold.classifier import FixtureClassifier
from app.modules.rulepacks.loader import RulePackLoader

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / "evals" / "gold-set" / "manifest.yaml"


def test_load_manifest_has_fifty_cases():
    cases = load_manifest(MANIFEST)
    assert len(cases) == 50
    assert cases[0].input_dir.exists()
    assert cases[0].expected_path.exists()


def test_load_expected_reads_critical_patterns(tmp_path):
    path = tmp_path / "expected.yaml"
    path.write_text(
        yaml.dump(
            {
                "critical_patterns": ["price_escalation_barred", "payment_terms_extended"],
                "optional_patterns": ["defect_liability_retention"],
                "max_noise": 2,
            }
        )
    )
    expected = load_expected(path)
    assert len(expected.critical_patterns) == 2
    assert expected.max_noise == 2


def test_score_case_counts_hits_noise_and_recall(tmp_path):
    expected_path = tmp_path / "expected.yaml"
    expected_path.write_text(
        yaml.dump(
            {
                "critical_patterns": ["a", "b"],
                "optional_patterns": ["c"],
                "max_noise": 1,
            }
        )
    )
    case = GoldCase(
        id="test-01",
        slice="government_works",
        input_dir=tmp_path,
        expected_path=expected_path,
    )
    findings = [
        {"pattern_id": "a"},
        {"pattern_id": "c"},
        {"pattern_id": "noise"},
    ]
    scored = score_case(case, findings)
    assert scored.critical_hits == 1
    assert scored.optional_hits == 1
    assert scored.noise == 1
    assert scored.critical_recall == 0.5
    assert scored.overall_recall == 2 / 3


def test_score_m5_aggregates_case_scores(tmp_path):
    expected_path = tmp_path / "expected.yaml"
    expected_path.write_text(yaml.dump({"critical_patterns": ["a"], "optional_patterns": []}))
    case = GoldCase("a", "s", tmp_path, expected_path)
    scored = score_case(case, [{"pattern_id": "a"}])
    result = score_m5([scored])
    assert result.cases_graded == 1
    assert result.critical_recall == 1.0


def test_fixture_classifier_returns_gold_answer_patterns():
    input_dir = REPO / "evals" / "in-works" / "sample_tender"
    clf = FixtureClassifier(input_dir)
    pack = RulePackLoader().get_pack("in-works")
    pattern = pack.patterns["liquidated_damages_uncapped"]
    clauses = [
        {
            "id": "c1",
            "clause_ref": "4",
            "text": "1% (one percent) of the contract value shall be levied for each week",
            "page_from": 4,
        }
    ]
    results = clf.classify(pattern, clauses)
    assert len(results) == 1
    assert results[0]["found"] is True
    assert "contract value" in results[0]["source_quote"]


def test_gold_set_manifest_slices_match_spec_table():
    cases = load_manifest(MANIFEST)
    slices: dict[str, int] = {}
    for case in cases:
        slices[case.slice] = slices.get(case.slice, 0) + 1
    assert slices == {
        "loss_maker": 5,
        "government_works": 15,
        "nhai_railways": 5,
        "private_developer": 5,
        "scanned_poor": 5,
        "mep_sae": 10,
        "saudi_gcc": 5,
    }
