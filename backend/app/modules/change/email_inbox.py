"""Forward-to-inbox email adapter (TS-247).

Inbound correspondence is untrusted — bodies are sanitized before classification.
Webhook signatures are HMAC-SHA256 over the raw request body.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from app.core.prompt_guard import sanitize_message


def generate_inbox_token() -> str:
    return secrets.token_urlsafe(12)


def build_forward_address(token: str, domain: str) -> str:
    return f"change-{token}@{domain}"


def verify_inbound_signature(body: bytes, signature: str | None, secret: str | None) -> bool:
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip())


def compose_signal_text(*, subject: str | None, body_plain: str) -> str:
    subject_line = (subject or "").strip()
    body = sanitize_message((body_plain or "").strip(), max_len=50_000)
    if subject_line:
        return f"Subject: {sanitize_message(subject_line, max_len=500)}\n\n{body}"
    return body
