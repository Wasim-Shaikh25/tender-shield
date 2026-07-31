#!/usr/bin/env python3
"""Score the M5 human gold set against the eval pipeline (TS-233).

Usage:
    python scripts/eval_gold_set.py
    python scripts/eval_gold_set.py --output evals/runs/gold-set/goldset.json
    python scripts/eval_gold_set.py --null-classifier   # absence-only smoke
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))

from app.evalcorpus.store import CorpusStore
from app.evalgold import load_manifest, score_case, score_m5
from app.evalgold.classifier import FixtureClassifier
from app.evalrunner.pipeline import _pipeline_pass
from app.modules.risk.classifier import NullClassifier
from app.modules.rulepacks.loader import RulePackLoader


class _InlineStore(CorpusStore):
    """Corpus store that serves inline document text for gold-set runs."""

    def __init__(self, inline_docs: dict[str, str]):
        super().__init__(Path("/dev/null"))
        self._inline = inline_docs

    def read_blob(self, digest: str) -> bytes | None:
        if digest in self._inline:
            return self._inline[digest].encode("utf-8")
        return None


def _run_case(case, pack, classifier) -> list[dict]:
    input_dir = case.input_dir
    gcc = input_dir / "conditions.md"
    if not gcc.exists():
        raise FileNotFoundError(f"missing input for {case.id}: {gcc}")
    text = gcc.read_text()
    inline = {"inline-conditions": text}
    docs = [
        {
            "title": "conditions.md",
            "url": str(gcc),
            "sha256": "inline-conditions",
        }
    ]
    boq = input_dir / "boq.csv"
    if boq.exists():
        inline["inline-boq"] = boq.read_text()
        docs.append({"title": "boq.csv", "url": str(boq), "sha256": "inline-boq"})

    store = _InlineStore(inline)
    _pages, findings, _clauses, _text, _boq = _pipeline_pass(
        docs, store, pack=pack, classifier=classifier, ocr=None
    )
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--manifest", default=str(REPO / "evals" / "gold-set" / "manifest.yaml"))
    ap.add_argument("--output", help="write goldset.json summary")
    ap.add_argument("--limit", type=int, help="score only first N cases")
    ap.add_argument(
        "--null-classifier",
        action="store_true",
        help="use NullClassifier (absence-only; lower recall on synthetic fixtures)",
    )
    args = ap.parse_args()

    pack = RulePackLoader().get_pack("in-works")
    cases = load_manifest(args.manifest)
    if args.limit:
        cases = cases[: args.limit]

    scores = []
    for case in cases:
        if args.null_classifier:
            classifier = NullClassifier()
        else:
            classifier = FixtureClassifier(case.input_dir)
        findings = _run_case(case, pack, classifier)
        scores.append(score_case(case, findings))

    result = score_m5(scores)
    payload = result.summary()
    print(json.dumps(payload, indent=2))

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2))

    # Build Doc §19.5 bar: critical recall >= 90% green. Synthetic fixtures with
    # FixtureClassifier should meet that bar; NullClassifier is for plumbing only.
    threshold = 0.75 if args.null_classifier else 0.90
    if result.critical_recall is not None and result.critical_recall < threshold:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
