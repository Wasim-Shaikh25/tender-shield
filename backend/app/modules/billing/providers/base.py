"""Payment provider abstraction (Doc §7, §15.6; R-005 §A). `BillingService`
talks to this Protocol only — never to a provider SDK directly — so Stripe
(GCC/UK, TS-037) is a new file behind this interface, not a rewrite of
BillingService. Razorpay is the only implementation until live Stripe
credentials exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class OrderRequest:
    workspace_id: str
    amount_minor: int  # already net of discount/tax (R-006/R-007); minor units always
    currency: str  # INR | AED | GBP
    kind: str  # paygo | subscription
    plan: str | None
    opportunity_id: str | None
    idempotency_key: str
    notes: dict  # opaque reference only (e.g. {"intent_id": ...}) — never the grant itself


@dataclass(frozen=True)
class OrderHandle:
    provider: str
    order_id: str  # the provider's id — what the client SDK opens a checkout with
    amount_minor: int
    currency: str
    checkout_payload: dict  # provider-specific fields the client SDK needs


@dataclass(frozen=True)
class ProviderEvent:
    """Normalised shape every provider's webhook maps onto so BillingService
    never branches on a provider-specific payload shape. `type` is kept as the
    provider's own event name (Razorpay's names are already namespaced
    sensibly — `order.paid`, `subscription.activated` — so no translation
    layer is invented for a single-provider v1)."""

    provider: str
    event_id: str
    type: str
    amount_minor: int | None
    currency: str | None
    reference_id: str | None  # our payment_intents.id, round-tripped via notes
    raw: dict


class PaymentProvider(Protocol):
    name: str

    def create_order(self, req: OrderRequest) -> OrderHandle: ...
    def verify_webhook(self, raw_body: bytes, signature: str) -> bool: ...
    def parse_event(self, raw_body: bytes) -> ProviderEvent: ...
