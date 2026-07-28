"""Provider selection by workspace country (Doc §7 — Razorpay for India,
Stripe for GCC/UK). R-005 §A: IN -> razorpay; everything else is unpriced
until Stripe lands (TS-037)."""

from __future__ import annotations

from app.modules.billing.providers.razorpay import RazorpayProvider


def select_provider(settings, country: str = "IN"):
    """Returns None (not a NullProvider) when no live keys are configured —
    checkout must fail honestly (503), never fake a successful order."""
    if country == "IN" and settings.razorpay_key_id and settings.razorpay_key_secret:
        return RazorpayProvider(
            settings.razorpay_key_id,
            settings.razorpay_key_secret,
            settings.razorpay_webhook_secret,
        )
    return None
