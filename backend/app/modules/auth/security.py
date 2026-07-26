"""Pure security primitives (Doc §5) — no DB, no FastAPI, fully unit-testable
in isolation. Refactor freely: the module depends only on these signatures.
"""

from __future__ import annotations

import hashlib
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

_ph = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=2)


class AuthError(Exception):
    """Raised for any authentication failure (bad token, expired, etc.)."""


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
