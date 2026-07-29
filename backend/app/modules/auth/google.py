"""Sign in with Google helpers (TS-036)."""

from __future__ import annotations

import jwt


class GoogleClient:
    """Verifies Google OIDC ID tokens against Google's public JWKS."""

    KEYS_URL = "https://www.googleapis.com/oauth2/v3/certs"
    ISSUER = "https://accounts.google.com"
    ALT_ISSUER = "accounts.google.com"

    def __init__(self, settings) -> None:
        self.settings = settings

    def is_configured(self) -> bool:
        return bool(self.settings.google_client_id)

    def verify_id_token(self, id_token: str) -> dict:
        """Verify a Google ID token and return the claims (raises on failure)."""
        if not self.is_configured():
            raise RuntimeError("google not configured")

        # We do not want to pull in google-auth at import time; verify manually
        # with Google's public JWKS, exactly like the Apple path.
        import httpx

        jwks = httpx.get(self.KEYS_URL, timeout=10.0).json()
        kid = jwt.get_unverified_header(id_token).get("kid")
        key = next((k for k in jwks["keys"] if k["kid"] == kid), None)
        if not key:
            raise jwt.InvalidTokenError("no matching google key")

        signing_key = jwt.PyJWK(key)
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=self.settings.google_client_id,
            issuer=[self.ISSUER, self.ALT_ISSUER],
        )
        return claims
