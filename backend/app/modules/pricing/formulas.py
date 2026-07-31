"""Named, versioned loading formulas (TS-202).

Every formula referenced by a rulepack's `price_impact.formula` must be
registered here — pure functions over a `facts: dict[str, Any]`, never LLM
input, never free-form code evaluated from YAML. A formula returns the
loading in **minor currency units** or raises `MissingInputs` naming exactly
which required facts were absent; the engine (`loading.py`) converts that into
"no loading produced", never a default (`specs/modules/pricing-intel.md` §1).

Adding a formula: write the pure function, register it under a **new** name
(never repurpose an existing name — that would silently change historical
loadings), and add a worked-example test in `tests/test_pricing.py`
before any pattern references it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class MissingInputs(Exception):
    def __init__(self, missing: list[str]):
        super().__init__(f"missing required facts: {', '.join(missing)}")
        self.missing = missing


def _require(facts: dict[str, Any], names: list[str]) -> list[Any]:
    missing = [n for n in names if facts.get(n) is None]
    if missing:
        raise MissingInputs(missing)
    return [facts[n] for n in names]


def escalation_unhedged(
    facts: dict[str, Any], *, contract_value_minor: int
) -> int:
    """Unhedged input-cost inflation exposure on a firm-price/no-escalation
    contract: contract_value x expected index movement over the duration.

    `index_series` is a fact carrying an annualized rate (e.g. 0.06 for 6%/yr)
    from a public index the caller resolved — this formula never fetches or
    assumes one itself.
    """
    duration_months, annual_rate = _require(
        facts, ["project_duration_months", "index_series"]
    )
    years = float(duration_months) / 12.0
    exposure_fraction = float(annual_rate) * years
    return round(contract_value_minor * exposure_fraction)


def ld_exposure_cap(
    facts: dict[str, Any], *, contract_value_minor: int
) -> int:
    """Bounded maximum LD exposure: rate_percent_per_week x weeks_at_risk,
    capped at cap_percent of contract value.

    Requires an explicit `cap_percent`. An uncapped LD clause (no cap fact
    extracted) correctly produces **no loading** here — this formula cannot
    bound an unbounded exposure, and guessing a cap would be exactly the
    invented number the product exists to prevent. That is the point of the
    finding itself, not a gap in this formula.
    """
    rate_pct, cap_pct, weeks = _require(
        facts, ["rate_percent_per_week", "cap_percent", "weeks_at_risk"]
    )
    raw_fraction = (float(rate_pct) / 100.0) * float(weeks)
    capped_fraction = min(raw_fraction, float(cap_pct) / 100.0)
    return round(contract_value_minor * capped_fraction)


def payment_delay_financing_cost(
    facts: dict[str, Any], *, contract_value_minor: int
) -> int:
    """Financing cost of extended payment terms beyond a 30-day baseline:
    (payment_days - 30) days of contract value financed at cost_of_capital_pa.
    """
    payment_days, cost_of_capital_pa = _require(
        facts, ["payment_days", "cost_of_capital_pa"]
    )
    extra_days = max(float(payment_days) - 30.0, 0.0)
    daily_rate = float(cost_of_capital_pa) / 365.0
    return round(contract_value_minor * daily_rate * extra_days)


FORMULAS: dict[str, Callable[..., int]] = {
    "escalation_unhedged": escalation_unhedged,
    "ld_exposure_cap": ld_exposure_cap,
    "payment_delay_financing_cost": payment_delay_financing_cost,
}


def get_formula(name: str) -> Callable[..., int] | None:
    return FORMULAS.get(name)
