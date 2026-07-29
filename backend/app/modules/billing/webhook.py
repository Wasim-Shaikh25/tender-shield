"""Razorpay webhook signature verification (Doc §7, §15.5) — pure. The webhook
is the ONLY billing truth; client redirects activate nothing. HMAC-SHA256 over
the raw body, constant-time compared."""

from __future__ import annotations

import hashlib
import hmac

from pydantic import SecretStr


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
