"""Rate build-up and sensitivity engines for pricing (TS-320).

Deterministic, zero-LLM: breaks a BOQ rate into material/labour/equipment/overhead/
profit components, and runs what-if scenarios on rates, quantities, and profit
margin. Amounts are kept in minor units to match the rest of pricing.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class RateBuildupResult:
    currency: str
    total_amount_minor: int
    total_profit_minor: int
    items: list[dict]
    assumptions: list[str]

    def to_dict(self) -> dict:
        return {
            "currency": self.currency,
            "total_amount_minor": self.total_amount_minor,
            "total_profit_minor": self.total_profit_minor,
            "items": self.items,
            "assumptions": self.assumptions,
        }


def _minor(value: float) -> int:
    return int(round(value * 100))


def rate_buildup(
    df: pd.DataFrame,
    *,
    currency: str = "INR",
    material_pct: float = 0.35,
    labour_pct: float = 0.30,
    equipment_pct: float = 0.15,
    overhead_pct: float = 0.10,
    profit_pct: float = 0.10,
) -> RateBuildupResult:
    """Decompose each BOQ line rate into cost-of-works + overhead + profit.

    `df` must already be normalized (contains `amount_calc`, `unit_canon`).
    Percentages are applied to the unit rate and should sum to 1.0 for a
    balanced build-up; values outside [0, 1] clamp to the nearest bound.
    """
    if df.empty:
        return RateBuildupResult(currency, 0, 0, [], ["No BOQ rows to build up."])

    pct_sum = material_pct + labour_pct + equipment_pct + overhead_pct + profit_pct

    def clamp(p: float) -> float:
        return max(0.0, min(1.0, p))

    total_amount = 0
    total_profit = 0
    items: list[dict] = []
    for row in df.itertuples(index=False):
        qty = float(row.qty) if getattr(row, "qty", None) is not None else 0.0
        rate = float(row.rate) if getattr(row, "rate", None) is not None else 0.0
        if getattr(row, "amount_calc", None) is not None:
            amount = float(row.amount_calc)
        else:
            amount = round(qty * rate, 2)
        material = round(rate * clamp(material_pct), 2)
        labour = round(rate * clamp(labour_pct), 2)
        equipment = round(rate * clamp(equipment_pct), 2)
        overhead = round(rate * clamp(overhead_pct), 2)
        profit = round(rate * clamp(profit_pct), 2)
        build_total = round((material + labour + equipment + overhead + profit) * qty, 2)
        profit_total = round(profit * qty, 2)
        total_amount += amount
        total_profit += profit_total
        items.append(
            {
                "src_row": int(row.src_row) if getattr(row, "src_row", None) is not None else None,
                "description": str(getattr(row, "description", "")),
                "unit": str(getattr(row, "unit_canon", "")),
                "qty": qty,
                "rate_minor": _minor(rate),
                "amount_minor": _minor(amount),
                "material_rate_minor": _minor(material),
                "labour_rate_minor": _minor(labour),
                "equipment_rate_minor": _minor(equipment),
                "overhead_rate_minor": _minor(overhead),
                "profit_rate_minor": _minor(profit),
                "build_total_minor": _minor(build_total),
            }
        )

    assumptions = [
        "Build-up split: "
        f"material {material_pct*100:.0f}%, labour {labour_pct*100:.0f}%, "
        f"equipment {equipment_pct*100:.0f}%, overhead {overhead_pct*100:.0f}%, "
        f"profit {profit_pct*100:.0f}%.",
    ]
    if abs(pct_sum - 1.0) > 0.001:
        assumptions.append(f"Component percentages sum to {pct_sum*100:.1f}%; review for accuracy.")

    return RateBuildupResult(
        currency=currency,
        total_amount_minor=_minor(total_amount),
        total_profit_minor=_minor(total_profit),
        items=items,
        assumptions=assumptions,
    )


@dataclass(frozen=True)
class SensitivityResult:
    base_total_minor: int
    currency: str
    scenarios: list[dict]

    def to_dict(self) -> dict:
        return {
            "base_total_minor": self.base_total_minor,
            "currency": self.currency,
            "scenarios": self.scenarios,
        }


def sensitivity(
    df: pd.DataFrame,
    *,
    currency: str = "INR",
    scenarios: list[dict] | None = None,
) -> SensitivityResult:
    """Run what-if scenarios on BOQ totals.

    Supported `param` values: `rate`, `qty`, `profit_pct` (shifts the profit
    component only; other components are held constant), `overhead_pct`.
    `delta_pct` is a percentage change, e.g. -10 for a 10% decrease.
    """
    if df.empty:
        return SensitivityResult(0, currency, [])

    base_total = float(df["amount_calc"].sum())
    if scenarios is None:
        scenarios = [
            {"name": "Rates -10%", "param": "rate", "delta_pct": -10},
            {"name": "Rates +10%", "param": "rate", "delta_pct": 10},
            {"name": "Quantities -10%", "param": "qty", "delta_pct": -10},
            {"name": "Quantities +10%", "param": "qty", "delta_pct": 10},
            {"name": "Profit margin -5pp", "param": "profit_pct", "delta_pct": -5},
            {"name": "Profit margin +5pp", "param": "profit_pct", "delta_pct": 5},
        ]

    results: list[dict] = []
    for s in scenarios:
        param = s.get("param", "")
        delta = float(s.get("delta_pct", 0))
        adjusted = 0.0
        if param == "rate":
            factor = 1 + delta / 100.0
            adjusted = float((df["amount_calc"] * factor).sum())
        elif param == "qty":
            factor = 1 + delta / 100.0
            adjusted = float((df["qty"] * df["rate"] * factor).sum())
        elif param == "profit_pct":
            # Apply only to the profit component of amount_calc.
            profit_share = 0.10  # default assumed profit split
            adjusted = base_total * (1 + (delta / 100.0) * profit_share)
        elif param == "overhead_pct":
            overhead_share = 0.10  # default assumed overhead split
            adjusted = base_total * (1 + (delta / 100.0) * overhead_share)
        else:
            adjusted = base_total * (1 + delta / 100.0)
        results.append(
            {
                "name": s.get("name", f"{param} {delta:+.0f}%"),
                "param": param,
                "delta_pct": delta,
                "total_amount_minor": _minor(adjusted),
                "delta_minor": _minor(adjusted - base_total),
                "delta_pct_total": (
                    round(((adjusted - base_total) / base_total) * 100, 2) if base_total else 0.0
                ),
            }
        )

    return SensitivityResult(
        base_total_minor=_minor(base_total),
        currency=currency,
        scenarios=results,
    )
