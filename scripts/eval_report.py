#!/usr/bin/env python3
"""Generate scorecard.md and regressions.md for a run (TS-231).

Thin CLI over `app.evalrunner.report`; the logic lives in the backend package so
it is typed, linted and covered by the normal test suite.

Usage:
    python scripts/eval_report.py --run-id smoke1
    python scripts/eval_report.py --run-id nightly-20260731 --baseline nightly-20260730

Without --baseline, the most recent other run on the same corpus + shard is used
automatically. If none exists, this run becomes the baseline for future ones and
regressions.md says so rather than treating it as an error.

Exit code is 1 when any headline metric regressed by more than the bar in
`specs/eval-at-scale.md` §3.4 (Build Doc §11.5: >2pt drop blocks the change).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))

from app.evalrunner.report import diff_metrics, load_run, write_report

DEFAULT_RUNS = REPO / "evals" / "runs"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--runs-root", default=str(DEFAULT_RUNS))
    ap.add_argument("--baseline", help="run_id to diff against; auto-detected if omitted")
    args = ap.parse_args()

    run_dir = Path(args.runs_root) / args.run_id
    if not run_dir.exists():
        print(f"error: no such run: {run_dir}", file=sys.stderr)
        return 2

    if args.baseline:
        baseline_dir = Path(args.runs_root) / args.baseline
        if not baseline_dir.exists():
            print(f"error: no such baseline run: {baseline_dir}", file=sys.stderr)
            return 2
        # write_report auto-detects; honor an explicit --baseline by diffing
        # separately and rewriting regressions.md over its output.
        from app.evalrunner.report import compute_metrics, render_regressions

        run = load_run(run_dir)
        baseline_run = load_run(baseline_dir)
        current_metrics = compute_metrics(run)
        baseline_metrics = compute_metrics(baseline_run)
        findings = diff_metrics(baseline_metrics, current_metrics)
        (run_dir / "regressions.md").write_text(
            render_regressions(baseline_run, run, findings)
        )
        from app.evalrunner.report import render_scorecard

        (run_dir / "scorecard.md").write_text(render_scorecard(run, current_metrics))
    else:
        _current_metrics, findings = write_report(run_dir, args.runs_root)

    print((run_dir / "scorecard.md").read_text())
    print((run_dir / "regressions.md").read_text())

    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
