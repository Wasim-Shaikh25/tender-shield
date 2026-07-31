"""Tests for M4 metamorphic consistency (TS-229)."""

from app.evalmetamorphic import check_order_invariance, check_redundancy_invariance, run_m4


def _finding(kind="risk_clause", category="payment", pattern_id="p1", title="A"):
    return {
        "kind": kind,
        "category": category,
        "pattern_id": pattern_id,
        "title": title,
        "severity": "high",
    }


def test_order_invariance_passes_when_findings_match():
    base = [_finding(), _finding(title="B", pattern_id="p2")]
    shuffled = [_finding(pattern_id="p2", title="B"), _finding()]
    check = check_order_invariance(base, shuffled)
    assert check.passed is True


def test_order_invariance_fails_when_findings_differ():
    base = [_finding()]
    other = [_finding(), _finding(title="extra", pattern_id="p2")]
    check = check_order_invariance(base, other)
    assert check.passed is False


def test_redundancy_invariance_passes_for_same_set():
    base = [_finding()]
    check = check_redundancy_invariance(base, list(base))
    assert check.passed is True


def test_run_m4_aggregates_checks():
    base = [_finding()]
    result = run_m4(base, {"shuffled": list(base), "redundant": list(base)})
    assert result.ok is True
    assert len(result.checks) == 2
