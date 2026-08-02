#!/usr/bin/env python3
"""CI eval smoke gate — 20-tender M1 + M4 slice (TS-232).

Builds a small offline corpus from fixtures, runs bulk_eval with M4 checks,
and writes a scorecard. Exit code 1 on M1 or M4 failure.

Usage:
    python scripts/eval_ci_smoke.py
    python scripts/eval_ci_smoke.py --limit 5   # faster local check
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))

from app.evalcorpus.adapters import OcdsFileAdapter
from app.evalcorpus.harvest import harvest
from app.evalcorpus.store import CorpusStore

GCC_TEXT = (
    b"[p1]\nGENERAL CONDITIONS OF CONTRACT\n"
    b"[p5]\nLiquidated damages for delay shall be levied at the rate of "
    b"1% per week of the contract value, with no maximum cap."
)

NIT_TEXT = (
    b"[p1]\nNOTICE INVITING TENDER\n"
    b"Name of Employer: PWD Division I\n"
    b"Estimated cost: INR 1000.00\n"
    b"Last date of submission: 15/08/2026 15:00\n"
    b"Time for completion: 24 months\n"
)


def _build_smoke_corpus(root: Path, *, n: int) -> Path:
    src = root / "src"
    src.mkdir(parents=True)
    gcc = src / "gcc.md"
    gcc.write_bytes(GCC_TEXT)
    nit = src / "nit.md"
    nit.write_bytes(NIT_TEXT)
    documents = [
        {"url": gcc.as_uri(), "documentType": "gcc", "title": "gcc.md"},
        {"url": nit.as_uri(), "documentType": "nit", "title": "nit.md"},
    ]
    template = {
        "buyer": {"name": "PWD Division I", "address": {"countryName": "India"}},
        "tender": {
            "value": {"amount": "1000.00", "currency": "INR"},
            "tenderPeriod": {
                "startDate": "2026-07-01T00:00:00Z",
                "endDate": "2026-08-15T15:00:00Z",
            },
            "contractPeriod": {
                "startDate": "2026-09-01T00:00:00Z",
                "endDate": "2028-09-01T00:00:00Z",
            },
            "documents": documents,
        },
    }
    releases = [
        dict(template, ocid=f"ocds-smoke-{i}", id=str(i)) for i in range(n)
    ]
    (src / "package.json").write_text(json.dumps({"releases": releases}))
    corpus = root / "corpus"
    harvest(OcdsFileAdapter(src), CorpusStore(corpus), include_awards=False)
    return corpus


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--limit", type=int, default=20, help="tenders in smoke slice (default 20)")
    ap.add_argument("--run-id", default="ci-smoke")
    args = ap.parse_args()

    with tempfile.TemporaryDirectory(prefix="ts-eval-smoke-") as tmp:
        tmp_path = Path(tmp)
        corpus = _build_smoke_corpus(tmp_path, n=args.limit)
        runs_root = tmp_path / "runs"

        bulk = subprocess.run(
            [
                sys.executable,
                str(REPO / "scripts" / "bulk_eval.py"),
                "--corpus",
                str(corpus),
                "--runs-root",
                str(runs_root),
                "--run-id",
                args.run_id,
                "--limit",
                str(args.limit),
                "--run-m4",
                "--concurrency",
                "2",
            ],
            cwd=REPO,
            check=False,
        )
        if bulk.returncode != 0:
            return bulk.returncode

        report = subprocess.run(
            [
                sys.executable,
                str(REPO / "scripts" / "eval_report.py"),
                "--run-id",
                args.run_id,
                "--runs-root",
                str(runs_root),
            ],
            cwd=REPO,
            check=False,
        )
        return report.returncode


if __name__ == "__main__":
    sys.exit(main())
