"""Tests for the scorecard / regression-diff generator (TS-231).

Builds run directories directly (bypassing the harvester/runner, already tested
in test_evalcorpus.py and test_evalrunner.py) so these tests focus purely on
report generation: metric computation, baseline auto-detection, regression
thresholds, and that "not yet available" is reported honestly rather than
faked.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.evalrunner.report import (
    compute_metrics,
    diff_metrics,
    find_baseline,
    load_run,
    render_regressions,
    render_scorecard,
    write_report,
)


def _write_run(
    runs_root: Path,
    run_id: str,
    results: list[dict],
    *,
    corpus_root: str = "/corpus",
    shard: str = "0/1",
    started_at: str = "2026-07-31T00:00:00+00:00",
) -> Path:
    run_dir = runs_root / run_id
    run_dir.mkdir(parents=True)
    manifest = {
        "run_id": run_id,
        "corpus_root": corpus_root,
        "shard": shard,
        "started_at": started_at,
        "rulepack_version": "2026.07.1",
        "model_id": "none",
        "tenders_in_shard": len(results),
        "tenders_run": len(results),
        "tenders_cached": 0,
        "tenders_resumed_skip": 0,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest))
    with (run_dir / "results.jsonl").open("w") as fh:
        for r in results:
            fh.write(json.dumps(r) + "\n")
    return run_dir


def _ok_result(ocid: str, *, findings=2, wall=1.0, cost=100, m1_ok=True, violations=None) -> dict:
    violations = violations or {}
    return {
        "ocid": ocid,
        "status": "ok" if m1_ok else "failed",
        "failure_reason": None if m1_ok else "invariant_violation",
        "m1_ok": m1_ok,
        "m1_summary": {"violations_by_invariant": violations},
        "findings_count": findings,
        "boq_status": "not_applicable",
        "wall_seconds": wall,
        "token_count": 0,
        "cost_minor": cost,
        "fully_priced": True,
    }


# ------------------------------------------------------------------ load_run


def test_load_run_reads_manifest_and_results(tmp_path):
    run_dir = _write_run(tmp_path, "r1", [_ok_result("a"), _ok_result("b")])
    run = load_run(run_dir)
    assert run.run_id == "r1"
    assert len(run.results) == 2
    assert run.corpus_root == "/corpus"


def test_load_run_on_a_missing_run_is_empty(tmp_path):
    run = load_run(tmp_path / "nonexistent")
    assert run.manifest == {}
    assert run.results == []


# -------------------------------------------------------------- compute_metrics


def test_metrics_m1_pass_rate_all_pass(tmp_path):
    run = load_run(_write_run(tmp_path, "r1", [_ok_result("a"), _ok_result("b")]))
    m = compute_metrics(run)
    assert m.m1_pass_rate == 1.0
    assert m.quote_verbatim_rate == 1.0
    assert m.crash_rate == 0.0


def test_metrics_m1_pass_rate_partial(tmp_path):
    run = load_run(
        _write_run(
            tmp_path,
            "r1",
            [_ok_result("a"), _ok_result("b", m1_ok=False, violations={"quote_integrity": 1})],
        )
    )
    m = compute_metrics(run)
    assert m.m1_pass_rate == 0.5
    assert m.quote_verbatim_rate == 0.5
    assert m.violations_by_invariant == {"quote_integrity": 1}


def test_metrics_crash_rate_counts_only_crash_reasons(tmp_path):
    results = [
        _ok_result("a"),
        {
            "ocid": "b",
            "status": "failed",
            "failure_reason": "parse_failed",
            "m1_ok": None,
            "findings_count": 0,
            "wall_seconds": 0.5,
            "cost_minor": None,
            "fully_priced": True,
        },
        {
            "ocid": "c",
            "status": "failed",
            "failure_reason": "invariant_violation",  # not a crash reason
            "m1_ok": False,
            "m1_summary": {"violations_by_invariant": {"budget": 1}},
            "findings_count": 0,
            "wall_seconds": 0.5,
            "cost_minor": None,
            "fully_priced": True,
        },
    ]
    run = load_run(_write_run(tmp_path, "r1", results))
    m = compute_metrics(run)
    assert m.crash_rate == 1 / 3       # only "b"
    assert m.invariant_violation_rate == 1 / 3  # only "c"
    assert m.failure_reason_counts == {"parse_failed": 1, "invariant_violation": 1}


def test_metrics_cost_excludes_unpriced_tenders(tmp_path):
    results = [
        _ok_result("a", cost=100),
        dict(_ok_result("b", cost=200), fully_priced=False),
    ]
    run = load_run(_write_run(tmp_path, "r1", results))
    m = compute_metrics(run)
    # p50 of a single value (100) — the unpriced tenant is excluded entirely
    assert m.cost_minor["p50"] == 100


def test_metrics_on_empty_run_lists_not_yet_available(tmp_path):
    run = load_run(_write_run(tmp_path, "r1", []))
    m = compute_metrics(run)
    assert m.tenders_graded == 0
    assert m.m1_pass_rate is None
    assert any("TS-227" in item for item in m.not_yet_available)


def test_compute_metrics_aggregates_m2_when_present(tmp_path):
    result = _ok_result("a")
    result["m2_summary"] = {"graded_fields": 4, "matches": 3, "match_rate": 0.75}
    run = load_run(_write_run(tmp_path, "r1", [result]))
    m = compute_metrics(run)
    assert m.m2_match_rate == 0.75


def test_compute_metrics_aggregates_m4_when_present(tmp_path):
    result = _ok_result("a")
    result["m4_summary"] = {"ok": True, "checks": []}
    run = load_run(_write_run(tmp_path, "r1", [result]))
    m = compute_metrics(run)
    assert m.m4_pass_rate == 1.0


def test_metrics_never_fabricates_m2_m3_m5():
    """The whole point: metrics the harness cannot yet compute must be absent,
    not approximated from what IS available."""
    from app.evalrunner.report import Metrics

    m = Metrics()
    assert m.m2_match_rate is None
    assert m.m4_pass_rate is None
    assert not hasattr(m, "l1_backtest_mape")
    assert not hasattr(m, "gold_set_recall")


# ------------------------------------------------------------------- baseline


def test_find_baseline_picks_the_most_recent_prior_run_on_the_same_slice(tmp_path):
    _write_run(tmp_path, "old", [_ok_result("a")], started_at="2026-07-29T00:00:00+00:00")
    _write_run(tmp_path, "mid", [_ok_result("a")], started_at="2026-07-30T00:00:00+00:00")
    current = load_run(
        _write_run(tmp_path, "new", [_ok_result("a")], started_at="2026-07-31T00:00:00+00:00")
    )

    baseline = find_baseline(tmp_path, current)
    assert baseline is not None
    assert baseline.run_id == "mid"


def test_find_baseline_ignores_a_different_corpus_or_shard(tmp_path):
    _write_run(tmp_path, "other-corpus", [_ok_result("a")], corpus_root="/different")
    _write_run(tmp_path, "other-shard", [_ok_result("a")], shard="1/2")
    current = load_run(_write_run(tmp_path, "new", [_ok_result("a")]))

    assert find_baseline(tmp_path, current) is None


def test_find_baseline_none_when_this_is_the_first_run(tmp_path):
    current = load_run(_write_run(tmp_path, "first", [_ok_result("a")]))
    assert find_baseline(tmp_path, current) is None


def test_find_baseline_ignores_the_cache_directory(tmp_path):
    (tmp_path / "_cache").mkdir()
    current = load_run(_write_run(tmp_path, "r1", [_ok_result("a")]))
    assert find_baseline(tmp_path, current) is None  # does not crash on _cache


# --------------------------------------------------------------- diff_metrics


def test_diff_metrics_no_baseline_is_empty():
    from app.evalrunner.report import Metrics

    assert diff_metrics(None, Metrics()) == []


def test_diff_metrics_flags_a_2pt_m1_drop():
    from app.evalrunner.report import Metrics

    baseline = Metrics(m1_pass_rate=1.0)
    current = Metrics(m1_pass_rate=0.97)  # 3pt drop
    findings = diff_metrics(baseline, current)
    assert any(f.metric == "m1_pass_rate" for f in findings)


def test_diff_metrics_does_not_flag_a_small_drop():
    from app.evalrunner.report import Metrics

    baseline = Metrics(m1_pass_rate=1.0)
    current = Metrics(m1_pass_rate=0.99)  # 1pt drop, under the 2pt bar
    assert diff_metrics(baseline, current) == []


def test_diff_metrics_does_not_flag_an_improvement():
    from app.evalrunner.report import Metrics

    baseline = Metrics(m1_pass_rate=0.9)
    current = Metrics(m1_pass_rate=1.0)
    assert diff_metrics(baseline, current) == []


def test_diff_metrics_flags_a_crash_rate_increase_over_1pt():
    from app.evalrunner.report import Metrics

    baseline = Metrics(crash_rate=0.0)
    current = Metrics(crash_rate=0.02)
    findings = diff_metrics(baseline, current)
    assert any(f.metric == "crash_rate" for f in findings)


def test_diff_metrics_ignores_metrics_missing_on_either_side():
    from app.evalrunner.report import Metrics

    baseline = Metrics(m1_pass_rate=None)
    current = Metrics(m1_pass_rate=0.5)
    assert diff_metrics(baseline, current) == []


# ---------------------------------------------------------------- rendering


def test_render_scorecard_marks_perfect_m1_as_passing(tmp_path):
    run = load_run(_write_run(tmp_path, "r1", [_ok_result("a"), _ok_result("b")]))
    m = compute_metrics(run)
    md = render_scorecard(run, m)
    assert "M1 structural pass rate" in md
    assert "100.0%" in md
    assert "✅" in md


def test_render_scorecard_marks_imperfect_m1_as_failing(tmp_path):
    run = load_run(
        _write_run(
            tmp_path, "r1", [_ok_result("a", m1_ok=False, violations={"budget": 1})]
        )
    )
    m = compute_metrics(run)
    md = render_scorecard(run, m)
    assert "❌" in md


def test_render_scorecard_lists_not_yet_available_metrics(tmp_path):
    run = load_run(_write_run(tmp_path, "r1", [_ok_result("a")]))
    m = compute_metrics(run)
    md = render_scorecard(run, m)
    assert "TS-227" in md
    assert "TS-228" in md
    assert "TS-233" in md


def test_compute_metrics_reads_goldset_json(tmp_path):
    run_dir = _write_run(tmp_path, "r1", [_ok_result("a")])
    (run_dir / "goldset.json").write_text(
        json.dumps(
            {
                "critical_recall": 0.95,
                "overall_recall": 0.88,
                "noise_per_tender": 0.5,
            }
        )
    )
    run = load_run(run_dir)
    m = compute_metrics(run)
    assert m.m5_critical_recall == 0.95
    assert m.m5_overall_recall == 0.88
    assert m.m5_noise_per_tender == 0.5
    assert "Gold-set recall / critical recall / noise (M5) — TS-233" not in m.not_yet_available


def test_render_regressions_no_baseline():
    run = load_run(Path("/nonexistent"))
    md = render_regressions(None, run, [])
    assert "No prior run" in md


def test_render_regressions_no_regression(tmp_path):
    baseline = load_run(_write_run(tmp_path, "b", [_ok_result("a")]))
    current = load_run(_write_run(tmp_path, "c", [_ok_result("a")]))
    md = render_regressions(baseline, current, [])
    assert "No regression" in md


def test_render_regressions_lists_blocking_findings(tmp_path):
    from app.evalrunner.report import RegressionFinding

    baseline = load_run(_write_run(tmp_path, "b", [_ok_result("a")]))
    current = load_run(_write_run(tmp_path, "c", [_ok_result("a")]))
    finding = RegressionFinding("m1_pass_rate", 1.0, 0.9, -0.1, blocking=True)
    md = render_regressions(baseline, current, [finding])
    assert "BLOCKING" in md
    assert "m1_pass_rate" in md


# ------------------------------------------------------------------ write_report


def test_write_report_writes_both_files(tmp_path):
    run_dir = _write_run(tmp_path, "r1", [_ok_result("a")])
    metrics, findings = write_report(run_dir, tmp_path)
    assert (run_dir / "scorecard.md").exists()
    assert (run_dir / "regressions.md").exists()
    assert metrics.tenders_graded == 1
    assert findings == []  # no baseline yet


def test_write_report_detects_a_real_regression_end_to_end(tmp_path):
    _write_run(
        tmp_path, "baseline", [_ok_result("a"), _ok_result("b")],
        started_at="2026-07-30T00:00:00+00:00",
    )
    current_dir = _write_run(
        tmp_path,
        "current",
        [_ok_result("a"), _ok_result("b", m1_ok=False, violations={"quote_integrity": 1})],
        started_at="2026-07-31T00:00:00+00:00",
    )
    metrics, findings = write_report(current_dir, tmp_path)
    assert metrics.m1_pass_rate == 0.5
    assert any(f.metric == "m1_pass_rate" for f in findings)
    assert "BLOCKING" in (current_dir / "regressions.md").read_text()
