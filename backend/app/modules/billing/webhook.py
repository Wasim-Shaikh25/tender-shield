"""Razorpay + Stripe webhook signature verification (Doc §7, §15.5) — pure.
The webhook is the ONLY billing truth; client redirects activate nothing."""

from __future__ import annotations

import hashlib
import hmac
import logging

from pydantic import SecretStr

logger = logging.getLogger(__name__)


def _secret_to_bytes(secret: str | SecretStr | None) -> bytes:
    if secret is None:
        return b""
    if isinstance(secret, SecretStr):
        return (secret.get_secret_value() or "").encode()
    return secret.encode()


def verify_signature(raw_body: bytes, signature: str, secret: str | SecretStr | None) -> bool:
    secret_bytes = _secret_to_bytes(secret)
    if not signature or not secret_bytes:
        return False
    expected = hmac.new(secret_bytes, raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_stripe_signature(
    raw_body: bytes, signature: str, secret: str | SecretStr | None
) -> dict | None:
    """Verify a Stripe webhook signature and return the event dict, or None.

    Only `SignatureVerificationError` (bad signature) and `ValueError` (malformed
    payload) are swallowed; all other exceptions are allowed to propagate so SDK or
    runtime errors do not silently fail as a bad signature.
    """
    secret_value = _secret_to_bytes(secret).decode() if secret else ""
    if not signature or not secret_value:
        return None
    try:
        import stripe

        return stripe.Webhook.construct_event(
            payload=raw_body,
            sig_header=signature,
            secret=secret_value,
        )
    except stripe.error.SignatureVerificationError:
        return None
    except ValueError:
        return None
