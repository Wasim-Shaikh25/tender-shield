"""Unit tests for cost-code helpers (TS-240)."""

from app.modules.baseline.cost_codes import build_tree, compute_exposure_totals


def test_build_tree_nests_children():
    codes = [
        {"id": "1", "parent_id": None, "code": "01", "label": "Civil"},
        {"id": "2", "parent_id": "1", "code": "01.1", "label": "Earthworks"},
    ]
    tree = build_tree(codes)
    assert len(tree) == 1
    assert tree[0]["code"] == "01"
    assert tree[0]["children"][0]["code"] == "01.1"


def test_compute_exposure_totals_sums_minor_units():
    findings = [
        {"id": "f1", "amount_exposure": 100_00, "currency": "INR"},
        {"id": "f2", "amount_exposure": 50_00, "currency": "INR"},
    ]
    mappings = [
        {"cost_code_id": "c1", "finding_id": "f1"},
        {"cost_code_id": "c1", "finding_id": "f2"},
    ]
    totals = compute_exposure_totals(findings, mappings)
    assert totals["currency"] == "INR"
    assert totals["total_minor"] == 150_00
    assert totals["by_cost_code"][0]["amount_minor"] == 150_00
