#!/usr/bin/env python3
"""Run a pack's deterministic test cases (TS-220). Thin CLI over `app.packsdk.packtest`.

Usage:
    python scripts/pack_test.py --pack-dir rulepacks/in-works

Covers BOQ scope-gap / trade-checklist matching only — the offline, LLM-free
half of a pack. See `app/packsdk/__init__.py` for why risk-pattern judgment
cannot be verified this way. Exits 1 if any case fails or zero cases exist.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))

from app.packsdk import run_pack_tests


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pack-dir", required=True)
    ap.add_argument("--pack-id")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    result = run_pack_tests(args.pack_dir, args.pack_id)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"pack: {result.pack_id}  ({len(result.cases)} case(s))")
        for c in result.cases:
            status = "PASS" if c.passed else "FAIL"
            print(f"  [{status}] {c.case_file}")
            if c.error:
                print(f"         error: {c.error}")
            if c.missing_expected:
                print(f"         missing expected gaps: {c.missing_expected}")
            if c.unexpected_gaps:
                print(f"         unexpected gaps: {c.unexpected_gaps}")
        print(f"\n{'OK' if result.passed else 'FAILED'}")

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
