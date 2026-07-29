"""Credential-gated payment-provider adapters for checkout handles.

Razorpay and Stripe are the two planned providers; both degrade to deterministic
mock handles when live keys are absent so that the UI flow can be tested end-to-end
without real money moving.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from app.core.config import Settings

logger = logging.getLogger(__name__)


class BillingError(Exception):
    """Raised when a live payment provider cannot be used in production."""



class RazorpayProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: Any = None
        if settings.razorpay_key_id and settings.razorpay_key_secret:
            try:
                import razorpay

                self._client = razorpay.Client(
                    auth=(settings.razorpay_key_id, settings.razorpay_key_secret.get_secret_value())
                )
            except Exception as exc:
                logger.warning("razorpay client failed to initialise: %s", exc)

    def create_order(self, amount_minor: int, currency: str, notes: dict) -> dict:
        if not self._client:
            if self.settings.is_prod():
                raise BillingError("razorpay_not_configured")
            logger.info(
                "[razorpay-mock] order for %s %s with notes %s", amount_minor, currency, notes
            )
            return {
                "provider": "razorpay",
                "order_id": f"order_mock_{uuid.uuid4().hex[:12]}",
                "amount_minor": amount_minor,
                "currency": currency,
                "notes": notes,
                "mock": True,
            }
        try:
            order = self._client.order.create(
                {"amount": amount_minor, "currency": currency, "notes": notes}
            )
            return {
                "provider": "razorpay",
                "order_id": order["id"],
                "amount_minor": amount_minor,
                "currency": currency,
                "notes": notes,
                "mock": False,
            }
        except Exception as exc:
            logger.exception("razorpay order failed: %s", exc)
            raise


class StripeProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: Any = None
        if settings.stripe_secret_key:
            try:
                import stripe

                stripe.api_key = settings.stripe_secret_key.get_secret_value()
                self._client = stripe
            except Exception as exc:
                logger.warning("stripe client failed to initialise: %s", exc)

    def create_session(self, amount_minor: int, currency: str, metadata: dict) -> dict:
        if not self._client:
            if self.settings.is_prod():
                raise BillingError("stripe_not_configured")
            logger.info(
                "[stripe-mock] session for %s %s with metadata %s",
                amount_minor,
                currency,
                metadata,
            )
            return {
                "provider": "stripe",
                "session_id": f"cs_mock_{uuid.uuid4().hex[:12]}",
                "amount_minor": amount_minor,
                "currency": currency,
                "metadata": metadata,
                "mock": True,
            }
        try:
            session = self._client.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[
                    {
                        "price_data": {
                            "currency": currency.lower(),
                            "product_data": {"name": "TenderShield review"},
                            "unit_amount": amount_minor,
                        },
                        "quantity": 1,
                    }
                ],
                mode="payment",
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
                metadata=metadata,
            )
            return {
                "provider": "stripe",
                "session_id": session.id,
                "amount_minor": amount_minor,
                "currency": currency,
                "metadata": metadata,
                "mock": False,
            }
        except Exception as exc:
            logger.exception("stripe session failed: %s", exc)
            raise


def get_provider(settings: Settings, provider: str):
    if provider == "stripe":
        return StripeProvider(settings)
    return RazorpayProvider(settings)
