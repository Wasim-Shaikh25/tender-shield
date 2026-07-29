"""TOTP and one-time-code MFA primitives (Doc §5) — pure, offline, testable.
Optional; mandatory for owner/admin on Pro+ is enforced at login in a follow-up."""

from __future__ import annotations

import secrets

import pyotp

ISSUER = "TenderShield"
CODE_TTL_SECONDS = 300


def new_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, account: str) -> str:
    """otpauth:// URI for authenticator-app enrolment (QR)."""
    return pyotp.TOTP(secret).provisioning_uri(name=account, issuer_name=ISSUER)


def verify(secret: str, code: str) -> bool:
    if not secret or not code:
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def new_otp_code(length: int = 6) -> str:
    """Random numeric one-time code for email/SMS delivery."""
    return "".join(secrets.choice("0123456789") for _ in range(length))
