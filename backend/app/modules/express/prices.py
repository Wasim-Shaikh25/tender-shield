"""Server-owned Express tier prices (TS-211, audit TS-B01).

Money is always in minor units. Prices are never taken from the client.
"""

from __future__ import annotations

# Indicative prices from specs/modules/express-report.md (assumption).
EXPRESS_TIER_PRICES: dict[str, dict[str, int]] = {
    "INR": {
        "snapshot": 149_900,
        "risk": 499_900,
        "bidpack": 999_900,
    },
    "AED": {
        "snapshot": 7_500,
        "risk": 25_000,
        "bidpack": 50_000,
    },
    "GBP": {
        "snapshot": 1_499,
        "risk": 4_999,
        "bidpack": 9_999,
    },
}

COUNTRY_CURRENCY: dict[str, str] = {
    "IN": "INR",
    "AE": "AED",
    "SA": "AED",
    "QA": "AED",
    "GB": "GBP",
}
DEFAULT_COUNTRY = "IN"


def currency_for_country(country: str | None) -> str:
    return COUNTRY_CURRENCY.get((country or DEFAULT_COUNTRY).upper(), "INR")


def tier_price_minor(tier: str, *, country: str | None = None, currency: str | None = None) -> int:
    cur = (currency or currency_for_country(country)).upper()
    prices = EXPRESS_TIER_PRICES.get(cur) or EXPRESS_TIER_PRICES["INR"]
    if tier not in prices:
        raise ValueError("unknown_tier")
    return prices[tier]


def validate_express_amount(tier: str, currency: str, amount_minor: int) -> bool:
    try:
        return tier_price_minor(tier, currency=currency) == amount_minor
    except ValueError:
        return False
