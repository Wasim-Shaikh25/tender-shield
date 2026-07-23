"""Razorpay webhook signature verification (Doc §7, §15.5) — pure. The webhook
is the ONLY billing truth; client redirects activate nothing. HMAC-SHA256 over
the raw body, constant-time compared."""

from __future__ import annotations

import hashlib
import hmac


def verify_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    if not signature or not secret:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
