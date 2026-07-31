"""M4 metamorphic consistency checks (TS-229).

Robustness properties that need no ground truth — only two runs of the same
tender through the eval pipeline with controlled perturbations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def finding_fingerprints(findings: list[dict]) -> frozenset[str]:
    """Stable identity for a finding set — ignores ordering and ids."""
    parts = []
    for f in findings:
        parts.append(
            "|".join(
                [
                    str(f.get("kind") or ""),
                    str(f.get("category") or ""),
                    str(f.get("pattern_id") or ""),
                    str(f.get("title") or ""),
                    str(f.get("severity") or ""),
                ]
            )
        )
    return frozenset(sorted(parts))


@dataclass
class MetamorphicCheck:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class M4Result:
    checks: list[MetamorphicCheck] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.passed for c in self.checks)

    def summary(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "checks": [
                {"name": c.name, "passed": c.passed, "detail": c.detail} for c in self.checks
            ],
        }


def check_order_invariance(baseline: list[dict], shuffled: list[dict]) -> MetamorphicCheck:
    base = finding_fingerprints(baseline)
    other = finding_fingerprints(shuffled)
    passed = base == other
    detail = "" if passed else f"baseline={len(base)} shuffled={len(other)}"
    return MetamorphicCheck("order_invariance", passed, detail)


def check_redundancy_invariance(baseline: list[dict], redundant: list[dict]) -> MetamorphicCheck:
    base = finding_fingerprints(baseline)
    other = finding_fingerprints(redundant)
    passed = base == other
    detail = "" if passed else f"baseline={len(base)} redundant={len(other)}"
    return MetamorphicCheck("redundancy_invariance", passed, detail)


def run_m4(baseline_findings: list[dict], variants: dict[str, list[dict]]) -> M4Result:
    """Run configured metamorphic checks against variant finding sets."""
    checks: list[MetamorphicCheck] = []
    if "shuffled" in variants:
        checks.append(check_order_invariance(baseline_findings, variants["shuffled"]))
    if "redundant" in variants:
        checks.append(check_redundancy_invariance(baseline_findings, variants["redundant"]))
    return M4Result(checks=checks)
