"""Razorpay provider (Doc §7, §15). Real Orders API call over HTTPS via
httpx; requires TS_RAZORPAY_KEY_ID/TS_RAZORPAY_KEY_SECRET. With no keys
configured, BillingService never constructs this — checkout returns
503 payment_provider_unavailable instead (R-005 §A), the same posture as
Apple/OCR/the LLM classifier elsewhere in this codebase: a real integration
that degrades honestly rather than faking success without credentials.
"""

from __future__ import annotations

import json

import httpx

from app.modules.billing.providers.base import OrderHandle, OrderRequest, ProviderEvent
from app.modules.billing.webhook import verify_signature

ORDERS_URL = "https://api.razorpay.com/v1/orders"


class RazorpayProvider:
    name = "razorpay"

    def __init__(self, key_id: str, key_secret: str, webhook_secret: str):
        self._key_id = key_id
        self._key_secret = key_secret
        self._webhook_secret = webhook_secret

    def create_order(self, req: OrderRequest) -> OrderHandle:
        # Razorpay dedupes on receipt when idempotency is needed; passing our
        # own key means retrying create_order for the same intent is safe.
        payload = {
            "amount": req.amount_minor,
            "currency": req.currency,
            "receipt": req.idempotency_key,
            "notes": req.notes,
        }
        resp = httpx.post(
            ORDERS_URL,
            json=payload,
            auth=(self._key_id, self._key_secret),
            timeout=10.0,
        )
        resp.raise_for_status()
        order = resp.json()
        return OrderHandle(
            provider=self.name,
            order_id=order["id"],
            amount_minor=order["amount"],
            currency=order["currency"],
            checkout_payload={
                "key": self._key_id,
                "order_id": order["id"],
                "amount": order["amount"],
                "currency": order["currency"],
            },
        )

    def verify_webhook(self, raw_body: bytes, signature: str) -> bool:
        return verify_signature(raw_body, signature, self._webhook_secret)

    def parse_event(self, raw_body: bytes) -> ProviderEvent:
        try:
            evt = json.loads(raw_body)
        except (ValueError, json.JSONDecodeError):
            evt = {}
        notes = _extract_notes(evt)
        return ProviderEvent(
            provider=self.name,
            event_id=evt.get("id", "") or "",
            type=evt.get("event", "unknown"),
            amount_minor=_extract_amount(evt),
            currency=_extract_currency(evt),
            reference_id=notes.get("intent_id"),
            raw=evt,
        )


def _extract_notes(evt: dict) -> dict:
    """Razorpay puts our notes on the entity inside payload.<type>.entity.notes."""
    payload = evt.get("payload", {})
    for wrapper in payload.values():
        entity = wrapper.get("entity", {}) if isinstance(wrapper, dict) else {}
        if "notes" in entity and isinstance(entity["notes"], dict):
            return entity["notes"]
    return {}


def _extract_amount(evt: dict) -> int | None:
    payload = evt.get("payload", {})
    for wrapper in payload.values():
        entity = wrapper.get("entity", {}) if isinstance(wrapper, dict) else {}
        amt = entity.get("amount")
        if isinstance(amt, (int, str)):
            try:
                return int(amt)
            except ValueError:
                continue
    return None


def _extract_currency(evt: dict) -> str | None:
    payload = evt.get("payload", {})
    for wrapper in payload.values():
        entity = wrapper.get("entity", {}) if isinstance(wrapper, dict) else {}
        cur = entity.get("currency")
        if isinstance(cur, str):
            return cur
    return None
