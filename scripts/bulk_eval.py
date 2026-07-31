#!/usr/bin/env python3
"""Run the eval pipeline over a harvested corpus, unattended (TS-230).

Thin CLI over `app.evalrunner`; the orchestration lives in the backend package
so it is typed, linted and covered by the normal test suite.

Usage:
    python scripts/bulk_eval.py --corpus evals/corpus --run-id smoke
    python scripts/bulk_eval.py --corpus evals/corpus --shard 0/4 --concurrency 8
    python scripts/bulk_eval.py --corpus evals/corpus --limit 20 --run-id ci-smoke

Resumable: re-running with the same --run-id skips tenders already present in
that run's results.jsonl. Cross-run idempotent: an identical (tender, rulepack
version, model) combination reuses a cached result from any prior run unless
--force is passed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))

from app.evalrunner import run_batch

DEFAULT_CORPUS = REPO / "evals" / "corpus"
DEFAULT_RUNS = REPO / "evals" / "runs"


def _parse_shard(value: str) -> tuple[int, int]:
    try:
        i, n = value.split("/")
        return int(i), int(n)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--shard must be i/n, e.g. 0/4") from exc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    ap.add_argument("--runs-root", default=str(DEFAULT_RUNS))
    ap.add_argument("--run-id", help="defaults to a UTC timestamp")
    ap.add_argument("--pack", default="in-works")
    ap.add_argument(
        "--model",
        default="none",
        help='OpenRouter model id, or "none" (default) to use NullClassifier — '
        "absence detection only, zero LLM spend",
    )
    ap.add_argument("--shard", type=_parse_shard, default=(0, 1))
    ap.add_argument("--limit", type=int)
    ap.add_argument("--force", action="store_true", help="ignore the resume/cache and re-run")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--max-total-tokens", type=int)
    ap.add_argument("--max-wall-seconds", type=float)
    ap.add_argument("--run-m4", action="store_true", help="run M4 metamorphic checks per tender")
    args = ap.parse_args()

    summary = run_batch(
        args.corpus,
        args.runs_root,
        run_id=args.run_id,
        pack_id=args.pack,
        model_id=args.model,
        shard=args.shard,
        limit=args.limit,
        force=args.force,
        concurrency=args.concurrency,
        max_total_tokens=args.max_total_tokens,
        max_wall_seconds=args.max_wall_seconds,
        run_m4_checks=args.run_m4,
    )
    print(json.dumps(summary.to_dict(), indent=2))

    if summary.aborted_by_cost_guard:
        print("warning: run aborted by cost guard; results are partial", file=sys.stderr)
    # M1's own bar is 100%; a bulk run that graded anything below that is the
    # signal CI should block on (specs/eval-at-scale.md §3.3).
    if summary.m1_pass_rate is not None and summary.m1_pass_rate < 1.0:
        return 1
    if args.run_m4 and summary.m4_pass_rate is not None and summary.m4_pass_rate < 1.0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
