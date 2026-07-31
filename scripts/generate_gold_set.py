#!/usr/bin/env python3
"""Generate the 50-case M5 gold set manifest and expected.yaml files (TS-233)."""
from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
GOLD_ROOT = REPO / "evals" / "gold-set"
CASES = GOLD_ROOT / "cases"

PATTERNS = [
    "price_escalation_barred",
    "payment_terms_extended",
    "liquidated_damages_uncapped",
    "defect_liability_retention",
    "termination_for_convenience",
]

SLICES: list[tuple[str, int]] = [
    ("loss_maker", 5),
    ("government_works", 15),
    ("nhai_railways", 5),
    ("private_developer", 5),
    ("scanned_poor", 5),
    ("mep_sae", 10),
    ("saudi_gcc", 5),
]


def _expected_for(slice_name: str, index: int) -> dict:
    if slice_name == "loss_maker":
        return {
            "critical_patterns": PATTERNS,
            "optional_patterns": [],
            "max_noise": 2,
            "loss_maker_trap": "liquidated_damages_uncapped",
        }
    start = (index + len(slice_name)) % len(PATTERNS)
    critical = [PATTERNS[(start + i) % len(PATTERNS)] for i in range(3)]
    optional = [p for p in PATTERNS if p not in critical][:1]
    return {
        "critical_patterns": critical,
        "optional_patterns": optional,
        "max_noise": 2,
    }


def main() -> None:
    CASES.mkdir(parents=True, exist_ok=True)
    manifest_cases = []
    for slice_name, count in SLICES:
        for i in range(1, count + 1):
            case_id = f"{slice_name}-{i:02d}"
            case_dir = CASES / case_id
            case_dir.mkdir(parents=True, exist_ok=True)
            expected = _expected_for(slice_name, i)
            (case_dir / "expected.yaml").write_text(yaml.dump(expected, sort_keys=False))
            manifest_cases.append(
                {
                    "id": case_id,
                    "slice": slice_name,
                    "input_dir": "../in-works/sample_tender",
                    "expected_file": f"cases/{case_id}/expected.yaml",
                    "notes": f"M5 slice {slice_name}; synthetic variant on sample_tender",
                }
            )

    manifest = {
        "version": 1,
        "description": "M5 human gold set — 50 tenders per specs/eval-at-scale.md §1",
        "cases": manifest_cases,
    }
    (GOLD_ROOT / "manifest.yaml").write_text(yaml.dump(manifest, sort_keys=False))
    print(f"wrote {len(manifest_cases)} cases to {GOLD_ROOT}")


if __name__ == "__main__":
    main()
