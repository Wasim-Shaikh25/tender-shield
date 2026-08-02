"""Risk-to-price loading engine (TS-203, TS-296).

Converts accepted risk findings into a rupee figure an estimator can add to a
rate — deterministically, over facts persisted on the finding and the opportunity
contract value, never over an LLM call (`CLAUDE.md` §4). Every loading shows the
formula and inputs that produced it; a finding whose pattern has no `price_impact`,
or whose required facts are unavailable, produces no loading and a stated reason
— never a defaulted value (`specs/modules/pricing-intel.md` §1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.modules.pricing.formulas import MissingInputs, get_formula


@dataclass(frozen=True)
class LoadingResult:
    finding_id: str
    pattern_id: str
    produced: bool
    amount_minor: int | None
    currency: str
    basis: str | None
    formula: str | None
    rulepack_version: str
    inputs_used: dict[str, Any] = field(default_factory=dict)
    missing_inputs: list[str] = field(default_factory=list)
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "pattern_id": self.pattern_id,
            "produced": self.produced,
            "amount_minor": self.amount_minor,
            "currency": self.currency,
            "basis": self.basis,
            "formula": self.formula,
            "rulepack_version": self.rulepack_version,
            "inputs_used": self.inputs_used,
            "missing_inputs": self.missing_inputs,
            "reason": self.reason,
        }


def compute_loadings(
    findings: list[Any],
    patterns: dict[str, Any],
    facts_by_finding: dict[str, dict[str, Any]],
    *,
    contract_value_minor: int,
    currency: str,
    rulepack_version: str,
) -> list[LoadingResult]:
    """`findings` are ORM rows or dicts exposing `id`, `pattern_id`,
    `review_status`. Only `review_status == "accepted"` findings are ever
    priced — enforced here even though callers are also expected to
    pre-filter, so this guarantee holds regardless of the caller
    (acceptance criterion 8)."""
    results: list[LoadingResult] = []
    for f in findings:
        review_status = _get(f, "review_status")
        if review_status != "accepted":
            continue
        finding_id = str(_get(f, "id"))
        pattern_id = _get(f, "pattern_id")
        pattern = patterns.get(pattern_id) if pattern_id else None
        impact = getattr(pattern, "price_impact", None) if pattern else None

        if impact is None:
            results.append(
                LoadingResult(
                    finding_id=finding_id,
                    pattern_id=pattern_id or "",
                    produced=False,
                    amount_minor=None,
                    currency=currency,
                    basis=None,
                    formula=None,
                    rulepack_version=rulepack_version,
                    reason="pattern has no price_impact declaration",
                )
            )
            continue

        formula_fn = get_formula(impact.formula)
        if formula_fn is None:
            results.append(
                LoadingResult(
                    finding_id=finding_id,
                    pattern_id=pattern_id,
                    produced=False,
                    amount_minor=None,
                    currency=currency,
                    basis=impact.basis,
                    formula=impact.formula,
                    rulepack_version=rulepack_version,
                    reason=f"formula {impact.formula!r} is not registered",
                )
            )
            continue

        facts = facts_by_finding.get(finding_id, {})
        try:
            amount = formula_fn(facts, contract_value_minor=contract_value_minor)
        except MissingInputs as exc:
            results.append(
                LoadingResult(
                    finding_id=finding_id,
                    pattern_id=pattern_id,
                    produced=False,
                    amount_minor=None,
                    currency=currency,
                    basis=impact.basis,
                    formula=impact.formula,
                    rulepack_version=rulepack_version,
                    missing_inputs=exc.missing,
                    reason="missing required facts",
                )
            )
            continue

        results.append(
            LoadingResult(
                finding_id=finding_id,
                pattern_id=pattern_id,
                produced=True,
                amount_minor=amount,
                currency=currency,
                basis=impact.basis,
                formula=impact.formula,
                rulepack_version=rulepack_version,
                inputs_used={k: facts.get(k) for k in impact.inputs},
            )
        )
    return results


def _get(obj: Any, name: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)
