"""Sign in with Apple helpers (TS-071)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import jwt
from pydantic import SecretStr


def _normalize_pem(key: str | SecretStr | None) -> str:
    if key is None:
        return ""
    if isinstance(key, SecretStr):
        raw = key.get_secret_value() or ""
    else:
        raw = key
    return raw.replace("\\n", "\n").strip()


class AppleClient:
    """Wraps the server-side pieces of Sign in with Apple: client-secret
    generation, code exchange, and id_token verification."""

    TOKEN_URL = "https://appleid.apple.com/auth/token"
    KEYS_URL = "https://appleid.apple.com/auth/keys"
    ISSUER = "https://appleid.apple.com"

    def __init__(self, settings):
        self.settings = settings

    def is_configured(self) -> bool:
        return all(
            [
                self.settings.apple_team_id,
                self.settings.apple_services_id,
                self.settings.apple_key_id,
                self.settings.apple_private_key,
            ]
        )

    def client_secret(self) -> str:
        now = datetime.now(UTC)
        payload = {
            "iss": self.settings.apple_team_id,
            "iat": now,
            "exp": now + timedelta(hours=1),
            "aud": self.ISSUER,
            "sub": self.settings.apple_services_id,
        }
        headers = {"kid": self.settings.apple_key_id}
        key = _normalize_pem(self.settings.apple_private_key)
        return jwt.encode(payload, key, algorithm="ES256", headers=headers)

    def exchange_code(self, code: str) -> dict:
        secret = self.client_secret()
        data = {
            "client_id": self.settings.apple_services_id,
            "client_secret": secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.settings.apple_redirect_uri,
        }
        r = httpx.post(self.TOKEN_URL, data=data, timeout=10.0)
        r.raise_for_status()
        return r.json()

    def verify_id_token(self, id_token: str) -> dict:
        jwks_client = jwt.PyJWKClient(self.KEYS_URL)
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)
        return jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=self.settings.apple_services_id,
            issuer=self.ISSUER,
        )
