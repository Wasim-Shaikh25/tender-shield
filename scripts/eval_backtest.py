#!/usr/bin/env python3
"""Run M3 outcome backtest on a harvested corpus (TS-228).

Usage:
    python scripts/eval_backtest.py --corpus evals/corpus
    python scripts/eval_backtest.py --corpus evals/corpus --output evals/runs/smoke/backtest.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))

from app.evalbacktest import run_m3_backtest
from app.evalcorpus.store import CorpusStore

DEFAULT_CORPUS = REPO / "evals" / "corpus"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    ap.add_argument("--output", help="write backtest.json to this path")
    ap.add_argument("--split-ratio", type=float, default=0.7)
    args = ap.parse_args()

    store = CorpusStore(args.corpus)
    tenders = store.iter_tenders()
    awards = []
    if store.awards_path.exists():
        for line in store.awards_path.read_text().splitlines():
            line = line.strip()
            if line:
                awards.append(json.loads(line))

    result = run_m3_backtest(tenders, awards, split_ratio=args.split_ratio)
    payload = result.summary()
    print(json.dumps(payload, indent=2))

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2))

    if result.test_count == 0:
        return 0  # corpus without awards is a valid no-op
    return 0


if __name__ == "__main__":
    sys.exit(main())
