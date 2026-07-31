"""Deterministic classifier for synthetic M5 fixtures (TS-233).

Reads ``gold_answer.yaml`` from the tender input directory so the eval pipeline
can score the gold set without an LLM API key. Only for planted synthetic
fixtures — real tenders still require human labels + a live classifier.
"""

from __future__ import annotations

from pathlib import Path

import yaml


class FixtureClassifier:
    """Returns gold-answer risk findings for patterns the engine retrieved."""

    def __init__(self, input_dir: Path):
        self._by_pattern: dict[str, dict] = {}
        gold_path = Path(input_dir) / "gold_answer.yaml"
        if gold_path.exists():
            raw = yaml.safe_load(gold_path.read_text()) or {}
            for row in raw.get("risk_findings") or []:
                pid = row.get("pattern")
                if pid:
                    self._by_pattern[pid] = row

    def classify(self, pattern, candidates):
        row = self._by_pattern.get(pattern.id)
        if not row or not candidates:
            return []
        return [
            {
                "found": True,
                "finding": row.get("quote") or pattern.title,
                "facts": {},
                "source_quote": row.get("quote") or "",
                "source_page": row.get("page"),
            }
        ]

    def provenance_meta(self, pattern, candidates) -> tuple[str, str | None]:
        return "fixture-gold-answer", None
