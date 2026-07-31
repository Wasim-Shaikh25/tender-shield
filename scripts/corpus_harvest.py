#!/usr/bin/env python3
"""Harvest public procurement records into the evaluation corpus (TS-224).

Thin CLI over `app.evalcorpus`; the logic lives in the backend package so it is
typed, linted and tested by the normal suite.

Usage:
    python scripts/corpus_harvest.py --list-adapters
    python scripts/corpus_harvest.py --source ocds-file --path <dir> --limit 100
    python scripts/corpus_harvest.py --source ocds-file --path <dir> --corpus evals/corpus
    python scripts/corpus_harvest.py --stats --corpus evals/corpus

Harvest rules (`specs/eval-at-scale.md` §2.3) are enforced by the adapters, not by
this script: public records only, robots.txt and published rate limits respected,
never anything behind authentication, and no customer documents — ever.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))

from app.evalcorpus import CorpusStore, harvest
from app.evalcorpus import adapters as adapter_registry

DEFAULT_CORPUS = REPO / "evals" / "corpus"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--source", help="adapter name (see --list-adapters)")
    ap.add_argument("--path", help="path argument for file-based adapters")
    ap.add_argument("--state", help="state code for state-nic adapter (e.g. maharashtra)")
    ap.add_argument("--dataset", help="dataset tag for ocds-registry adapter")
    ap.add_argument("--api-key", help="API key for network adapters that support it")
    ap.add_argument("--corpus", default=str(DEFAULT_CORPUS), help="corpus root directory")
    ap.add_argument("--limit", type=int, help="stop after N tenders")
    ap.add_argument("--no-documents", action="store_true", help="metadata only")
    ap.add_argument("--no-awards", action="store_true", help="skip award records")
    ap.add_argument(
        "--no-resume",
        action="store_true",
        help="re-harvest tenders already present in the manifest",
    )
    ap.add_argument("--list-adapters", action="store_true")
    ap.add_argument("--stats", action="store_true", help="print corpus stats and exit")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.list_adapters:
        for name in adapter_registry.available():
            print(name)
        return 0

    store = CorpusStore(args.corpus)

    if args.stats:
        print(json.dumps(store.stats(), indent=2))
        return 0

    if not args.source:
        ap.error("--source is required (or use --list-adapters / --stats)")

    kwargs = {}
    if args.path:
        kwargs["path"] = args.path
    if args.state:
        kwargs["state"] = args.state
    if args.dataset:
        kwargs["dataset"] = args.dataset
    if args.api_key:
        kwargs["api_key"] = args.api_key
    try:
        adapter = adapter_registry.build(args.source, **kwargs)
    except (KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    info = adapter.info
    print(f"adapter : {info.name} v{info.version} ({info.country})")
    print(f"legality: {info.legality}")
    print(f"corpus  : {store.root}")
    print("-" * 72)

    result = harvest(
        adapter,
        store,
        limit=args.limit,
        fetch_documents=not args.no_documents,
        include_awards=not args.no_awards,
        resume=not args.no_resume,
    )
    print(json.dumps(result.summary(), indent=2))
    # A run that wrote nothing and errored is a failure; partial success is success.
    return 1 if (result.errors and result.tenders_written == 0) else 0


if __name__ == "__main__":
    sys.exit(main())
