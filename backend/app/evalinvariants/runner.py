"""Aggregate the ten M1 checks into one pass/fail result (TS-226).

`run_m1` is the single entry point the bulk runner (TS-230) and CI (TS-232) call.
The bar is binary by design (`specs/eval-at-scale.md` §1): 100% pass, any failure
blocks release. There is no partial-credit scoring here — that is what M2–M5 are
for.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.evalinvariants.bundle import PipelineBundle
from app.evalinvariants.checks import ALL_CHECKS, Violation


@dataclass
class M1Result:
    opportunity_id: str
    violations: list[Violation] = field(default_factory=list)
    checks_run: int = 0

    @property
    def ok(self) -> bool:
        return not self.violations

    def by_invariant(self) -> dict[str, list[Violation]]:
        out: dict[str, list[Violation]] = {}
        for v in self.violations:
            out.setdefault(v.invariant, []).append(v)
        return out

    def summary(self) -> dict[str, object]:
        return {
            "opportunity_id": self.opportunity_id,
            "ok": self.ok,
            "checks_run": self.checks_run,
            "violation_count": len(self.violations),
            "violations_by_invariant": {
                k: len(v) for k, v in self.by_invariant().items()
            },
            "violations": [
                {"invariant": v.invariant, "message": v.message, "finding_ref": v.finding_ref}
                for v in self.violations
            ],
        }


def run_m1(bundle: PipelineBundle) -> M1Result:
    """Run every M1 check against one bundle. Never raises on a bad finding —
    an invariant violation is data, not an exception; only a bug in a check
    itself should raise, and that should fail loudly in CI rather than being
    swallowed into a false pass."""
    result = M1Result(opportunity_id=bundle.opportunity_id)
    for check in ALL_CHECKS:
        result.violations.extend(check(bundle))
        result.checks_run += 1
    return result
