"""Pure security primitives (Doc §5) — no DB, no FastAPI, fully unit-testable
in isolation. Refactor freely: the module depends only on these signatures.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ALGO = "RS256"
ISSUER = "tendershield"
AUDIENCE = "tendershield-api"
MFA_AUDIENCE = "tendershield-mfa"

COMMON_PASSWORDS = {"password", "12345678", "123456789", "qwerty123", "password123", "admin123"}

_ph = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=2)


class AuthError(Exception):
    """Raised for any authentication failure (bad token, expired, etc.)."""


def validate_password(password: str) -> None:
    """Enforce a baseline password policy.

    - at least 8 characters
    - at least one uppercase, one lowercase, one digit, one special character
    - not a trivial/common password
    """
    if len(password) < 8:
        raise ValueError("password_too_short")
    if not re.search(r"[A-Z]", password):
        raise ValueError("password_missing_uppercase")
    if not re.search(r"[a-z]", password):
        raise ValueError("password_missing_lowercase")
    if not re.search(r"\d", password):
        raise ValueError("password_missing_digit")
    if not re.search(r"[^A-Za-z0-9]", password):
        raise ValueError("password_missing_special")
    if password.lower() in COMMON_PASSWORDS:
        raise ValueError("password_too_common")


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, password)
    except VerifyMismatchError:
        return False


@dataclass(frozen=True)
class KeyPair:
    private_pem: str
    public_pem: str
    kid: str


def _kid_for(public_pem: str) -> str:
    return hashlib.sha256(public_pem.encode()).hexdigest()[:16]


def generate_keypair() -> KeyPair:
    """Ephemeral RSA keypair — dev/test only (Doc §5: prod keys come from SSM)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return KeyPair(private_pem, public_pem, _kid_for(public_pem))


def load_keypair(private_pem: str, public_pem: str) -> KeyPair:
    return KeyPair(private_pem, public_pem, _kid_for(public_pem))


def mint_access(
    keys: KeyPair,
    *,
    user_id: str,
    workspace_id: str,
    role: str,
    is_superadmin: bool = False,
    ttl: timedelta,
    now: datetime | None = None,
) -> str:
    now = now or datetime.now(UTC)
    return jwt.encode(
        {
            "sub": user_id,
            "workspace": workspace_id,
            "role": role,
            "is_superadmin": is_superadmin,
            "iat": now,
            "exp": now + ttl,
            "iss": ISSUER,
            "aud": AUDIENCE,
            "jti": str(uuid.uuid4()),
        },
        keys.private_pem,
        algorithm=ALGO,
        headers={"kid": keys.kid},
    )


def decode_access(token: str, public_pem: str) -> dict:
    try:
        return jwt.decode(token, public_pem, algorithms=[ALGO], audience=AUDIENCE, issuer=ISSUER)
    except jwt.PyJWTError as exc:
        raise AuthError(f"invalid_token: {exc}") from exc


def mint_mfa_token(
    keys: KeyPair,
    *,
    user_id: str,
    workspace_id: str,
    role: str,
    is_superadmin: bool = False,
    ttl: timedelta = timedelta(minutes=5),
    now: datetime | None = None,
) -> str:
    """Short-lived token issued after a valid password but before MFA verification."""
    now = now or datetime.now(UTC)
    return jwt.encode(
        {
            "sub": user_id,
            "workspace": workspace_id,
            "role": role,
            "is_superadmin": is_superadmin,
            "iat": now,
            "exp": now + ttl,
            "iss": ISSUER,
            "aud": MFA_AUDIENCE,
            "jti": str(uuid.uuid4()),
        },
        keys.private_pem,
        algorithm=ALGO,
        headers={"kid": keys.kid},
    )


def decode_mfa_token(token: str, public_pem: str) -> dict:
    try:
        return jwt.decode(
            token, public_pem, algorithms=[ALGO], audience=MFA_AUDIENCE, issuer=ISSUER
        )
    except jwt.PyJWTError as exc:
        raise AuthError(f"invalid_mfa_token: {exc}") from exc
