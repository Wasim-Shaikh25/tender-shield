#!/usr/bin/env python3
"""Validate a rule-pack (TS-220). Thin CLI over `app.packsdk.validate`.

Usage:
    python scripts/pack_validate.py --pack-dir rulepacks/in-works
    python scripts/pack_validate.py --pack-dir /path/to/my-pack

Exits 1 on any schema error or lint error (warnings do not fail the run).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))

from app.packsdk import validate_pack


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pack-dir", required=True, help="path to the pack root (contains pack.yaml)")
    ap.add_argument("--pack-id", help="defaults to the directory name")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    report = validate_pack(args.pack_dir, args.pack_id)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(f"pack: {report.pack_id}")
        if report.schema_errors:
            print(f"\nSCHEMA ERRORS ({len(report.schema_errors)}):")
            for path, msg in report.schema_errors.items():
                print(f"  ✗ {path}: {msg}")
        if report.errors:
            print(f"\nLINT ERRORS ({len(report.errors)}):")
            for i in report.errors:
                print(f"  ✗ [{i.code}] {i.message}")
        if report.warnings:
            print(f"\nWARNINGS ({len(report.warnings)}):")
            for i in report.warnings:
                print(f"  ! [{i.code}] {i.message}")
        print(f"\n{'OK' if report.ok else 'FAILED'}")

    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
