"""Deterministic pack test harness (TS-220).

Verifies the **offline, LLM-free** half of a pack — BOQ scope-gap and
trade-checklist matching (`app.modules.boq.engine.scope_gaps`, pure Python, no
API key) — against test cases a pack author writes themselves, independent of
the product's own test suite.

Risk-pattern *judgment* (does this clause text match this pattern?) is
LLM-graded and cannot be verified with a unit-test fixture — see the module
docstring in `__init__.py`. That half is what the scale-evaluation harness
(`specs/eval-at-scale.md`) exists for, against real documents at scale, not a
handful of hand-written cases.

Test-case format, one YAML file per case under `<pack>/tests/scope_gaps/`:

    checklist_id: hvac
    spec_text: |
      [p1]
      Provide air conditioning throughout via chilled water AHUs.
    boq_rows:
      - src_row: 1
        description: "Supply and install AHU"
        unit_raw: nos
        qty: 4
        rate: 500000
        amount: 2000000
    expect_gap_keys: [duct_insulation, condensate_drain]
    expect_no_gap_keys: []   # optional: keys that must NOT fire (a false positive check)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from app.modules.boq.engine import SpecTextIndex, normalize, scope_gaps
from app.modules.rulepacks.loader import RulePackLoader

_REQUIRED_BOQ_COLUMNS = {"src_row", "description", "unit_raw", "qty", "rate", "amount"}


@dataclass
class CaseResult:
    case_file: str
    passed: bool
    missing_expected: list[str] = field(default_factory=list)
    unexpected_gaps: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class PackTestResult:
    pack_id: str
    cases: list[CaseResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return bool(self.cases) and all(c.passed for c in self.cases)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pack_id": self.pack_id,
            "passed": self.passed,
            "case_count": len(self.cases),
            "cases": [
                {
                    "case_file": c.case_file,
                    "passed": c.passed,
                    "missing_expected": c.missing_expected,
                    "unexpected_gaps": c.unexpected_gaps,
                    "error": c.error,
                }
                for c in self.cases
            ],
        }


def _run_one_case(pack, case_path: Path) -> CaseResult:
    try:
        raw = yaml.safe_load(case_path.read_text()) or {}
    except yaml.YAMLError as exc:
        return CaseResult(case_path.name, passed=False, error=f"invalid YAML: {exc}")

    checklist_id = raw.get("checklist_id")
    if not checklist_id or checklist_id not in pack.trade_checklists:
        return CaseResult(
            case_path.name, passed=False, error=f"unknown checklist_id {checklist_id!r}"
        )

    boq_rows = raw.get("boq_rows") or []
    df = pd.DataFrame(boq_rows)
    missing_cols = _REQUIRED_BOQ_COLUMNS - set(df.columns)
    if missing_cols:
        return CaseResult(
            case_path.name, passed=False, error=f"boq_rows missing columns: {sorted(missing_cols)}"
        )

    try:
        normalized = normalize(df, pack.unit_canon)
        spec = SpecTextIndex(raw.get("spec_text", ""))
        findings = scope_gaps(normalized, spec, pack.trade_checklists[checklist_id])
    except Exception as exc:  # a malformed case must not crash the whole run
        return CaseResult(case_path.name, passed=False, error=f"{type(exc).__name__}: {exc}")

    fired_keys = {f.category for f in findings}
    expected = set(raw.get("expect_gap_keys") or [])
    forbidden = set(raw.get("expect_no_gap_keys") or [])

    missing_expected = sorted(expected - fired_keys)
    unexpected_gaps = sorted(forbidden & fired_keys)

    return CaseResult(
        case_path.name,
        passed=not missing_expected and not unexpected_gaps,
        missing_expected=missing_expected,
        unexpected_gaps=unexpected_gaps,
    )


def run_pack_tests(pack_dir: str | Path, pack_id: str | None = None) -> PackTestResult:
    pack_dir = Path(pack_dir)
    pack_id = pack_id or pack_dir.name
    loader = RulePackLoader(root=pack_dir.parent)
    pack = loader.get_pack(pack_dir.name, reload=True)

    cases_dir = pack_dir / "tests" / "scope_gaps"
    result = PackTestResult(pack_id=pack_id)
    if not cases_dir.is_dir():
        return result

    for case_path in sorted(cases_dir.glob("*.yaml")):
        result.cases.append(_run_one_case(pack, case_path))
    return result
