"""Working-capital / cashflow model (TS-206).

Deterministic month-by-month funding model over payment terms, retention,
mobilization advance, and a user-supplied cost of capital
(`specs/modules/pricing-intel.md` §3). Unlike the loading engine, missing
facts here are **allowed** to fall back to a stated default — but the default
must always be recorded in `assumptions[]`; nothing is silently substituted.

Simplifying, disclosed assumptions this model makes:

* Billing is even across the contract duration unless a milestone billing
  schedule is supplied.
* Incurred cost in a month equals that month's billed value (a common
  first-pass estimating simplification).
* `payment_days` is converted to whole months by ceiling division — a day-
  level model is out of scope for a monthly cashflow curve.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CashflowInputs:
    contract_value_minor: int
    duration_months: int
    cost_of_capital_pa: float  # required — never defaulted; the whole model is denominated in it
    payment_days: int | None = None
    retention_pct: float | None = None
    retention_release_month: int | None = None
    mobilization_advance_pct: float | None = None
    mobilization_recovery_months: int | None = None
    milestone_billing_minor: dict[int, int] | None = None  # {month: amount}


@dataclass(frozen=True)
class MonthlyPosition:
    month: int
    billed_minor: int
    incurred_minor: int
    received_minor: int
    cumulative_net_minor: int  # negative = funding required

    def to_dict(self) -> dict[str, Any]:
        return {
            "month": self.month,
            "billed_minor": self.billed_minor,
            "incurred_minor": self.incurred_minor,
            "received_minor": self.received_minor,
            "cumulative_net_minor": self.cumulative_net_minor,
        }


@dataclass(frozen=True)
class CashflowResult:
    monthly: list[MonthlyPosition]
    peak_requirement_minor: int
    peak_month: int
    total_financing_cost_minor: int
    currency: str
    assumptions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "monthly": [m.to_dict() for m in self.monthly],
            "peak_requirement_minor": self.peak_requirement_minor,
            "peak_month": self.peak_month,
            "total_financing_cost_minor": self.total_financing_cost_minor,
            "currency": self.currency,
            "assumptions": self.assumptions,
        }


def run_cashflow(inputs: CashflowInputs, *, currency: str) -> CashflowResult:
    assumptions: list[str] = []
    n = max(int(inputs.duration_months), 1)

    if inputs.milestone_billing_minor:
        billed = {m: inputs.milestone_billing_minor.get(m, 0) for m in range(1, n + 1)}
        billed_total = sum(inputs.milestone_billing_minor.values())
        if billed_total != inputs.contract_value_minor:
            assumptions.append(
                f"milestone billing schedule sums to {billed_total} minor units, "
                f"not the contract value {inputs.contract_value_minor}; used as supplied"
            )
    else:
        per_month = inputs.contract_value_minor // n
        remainder = inputs.contract_value_minor - per_month * n
        billed = {m: per_month for m in range(1, n + 1)}
        billed[n] += remainder  # keep the total exact; the remainder lands in the final month
        assumptions.append(
            "no milestone billing schedule supplied — assumed even monthly billing"
        )

    if inputs.payment_days is None:
        payment_delay_months = 1
        assumptions.append("payment_days not supplied — assumed 30 days (1 month)")
    else:
        payment_delay_months = max(math.ceil(inputs.payment_days / 30.0), 0)

    if inputs.retention_pct is None:
        retention_pct = 0.0
        assumptions.append("retention_pct not supplied — assumed 0%")
    else:
        retention_pct = inputs.retention_pct

    retention_release_month = inputs.retention_release_month
    if retention_pct > 0 and retention_release_month is None:
        retention_release_month = n
        assumptions.append(
            f"retention_release_month not supplied — assumed release at completion (month {n})"
        )

    mobilization_advance_minor = 0
    mobilization_recovery_months = 0
    if inputs.mobilization_advance_pct:
        mobilization_advance_minor = round(
            inputs.contract_value_minor * inputs.mobilization_advance_pct
        )
        mobilization_recovery_months = inputs.mobilization_recovery_months or n
        if inputs.mobilization_recovery_months is None:
            assumptions.append(
                "mobilization_recovery_months not supplied — assumed recovery over the "
                f"full duration ({n} months)"
            )

    total_retained = 0
    monthly: list[MonthlyPosition] = []
    cumulative_net = mobilization_advance_minor  # advance received up front, month 0

    for m in range(1, n + 1):
        billed_m = billed[m]
        incurred_m = billed_m  # disclosed simplification — see module docstring

        source_month = m - payment_delay_months
        gross_receivable = billed.get(source_month, 0) if source_month >= 1 else 0
        retained_this = round(gross_receivable * retention_pct)
        total_retained += retained_this
        received_m = gross_receivable - retained_this

        recovery = 0
        if mobilization_advance_minor and m <= mobilization_recovery_months:
            recovery = round(mobilization_advance_minor / mobilization_recovery_months)
        received_m -= recovery

        if retention_release_month == m:
            received_m += total_retained
            total_retained = 0

        cumulative_net += received_m - incurred_m
        monthly.append(
            MonthlyPosition(
                month=m,
                billed_minor=billed_m,
                incurred_minor=incurred_m,
                received_minor=received_m,
                cumulative_net_minor=cumulative_net,
            )
        )

    trough = min(monthly, key=lambda p: p.cumulative_net_minor)
    peak_requirement = max(-trough.cumulative_net_minor, 0)

    daily_rate = inputs.cost_of_capital_pa / 365.0
    # Financing cost: each month's shortfall (if any) costs one month of
    # daily_rate x 30 days — a monthly-resolution approximation, disclosed.
    financing_cost = 0
    for p in monthly:
        if p.cumulative_net_minor < 0:
            financing_cost += round(-p.cumulative_net_minor * daily_rate * 30)
    if any(p.cumulative_net_minor < 0 for p in monthly):
        assumptions.append(
            "financing cost approximated at monthly resolution (30 days per month), "
            "compounding not modeled"
        )

    return CashflowResult(
        monthly=monthly,
        peak_requirement_minor=peak_requirement,
        peak_month=trough.month,
        total_financing_cost_minor=financing_cost,
        currency=currency,
        assumptions=assumptions,
    )
