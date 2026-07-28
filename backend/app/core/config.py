from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven settings. All variables use the TS_ prefix."""

    model_config = SettingsConfigDict(env_prefix="TS_", extra="ignore")

    env: str = "dev"
    # PostgreSQL 16 in all deployed environments; SQLite only for local tests.
    database_url: str = "sqlite:///./tendershield.db"

    # DEV/TEST ONLY. Returns password-reset / invitation tokens directly in the
    # HTTP response so local flows work without an email provider wired up.
    # Enabling this in production is unauthenticated account takeover — anyone
    # who knows a user's email can read the reset token from the response and
    # take the account (R-002 §A). Startup refuses env=production + this true.
    dev_echo_tokens: bool = False

    def model_post_init(self, __context) -> None:
        if self.env == "production" and self.dev_echo_tokens:
            raise ValueError(
                "TS_DEV_ECHO_TOKENS must be false when TS_ENV=production — it "
                "returns password-reset/invitation tokens to unauthenticated callers"
            )

    # Uploaded-file storage root (LocalStorage in dev; S3 in prod, Doc §11.2).
    storage_dir: str = "./.tender_storage"

    # OCR for scanned PDFs (offline RapidOCR). Off by default (loads ONNX models
    # + needs the `ocr` extra); when off, scanned docs are flagged needs_ocr.
    ocr_enabled: bool = False

    # Auth (Doc §5). Keys are PEM strings; when absent an ephemeral RSA keypair
    # is generated at startup for dev/test only (never rely on it in prod).
    jwt_private_key: str = ""
    jwt_public_key: str = ""
    access_ttl_minutes: int = 15
    refresh_ttl_days: int = 30

    # CORS: comma-separated allowed origins for the browser SPA ("*" in dev).
    cors_origins: str = "*"

    # Base URL of the frontend SPA, used to build links in transactional email
    # (password reset, invitations).
    app_url: str = "http://localhost:3000"

    # Comma-separated peer IPs allowed to set X-Forwarded-For for rate-limit
    # client identity (R-002 §C). Empty = trust the immediate peer's IP as-is;
    # do NOT set this to "*" or a real client's own address, or a client can
    # spoof a fresh identity on every request and bypass rate limiting.
    trusted_proxies: str = ""

    def trusted_proxies_list(self) -> list[str]:
        return [p.strip() for p in self.trusted_proxies.split(",") if p.strip()]

    # Billing (Doc §7, §15). Webhook secret verifies the only billing truth.
    razorpay_webhook_secret: str = "dev-razorpay-secret"

    # Sign in with Apple (Doc §5). PEM private key may contain escaped newlines.
    apple_team_id: str = ""
    apple_services_id: str = ""
    apple_key_id: str = ""
    apple_private_key: str = ""
    apple_redirect_uri: str = ""

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()] or ["*"]

    # Comma-separated module names. Empty string means "discover everything
    # under app/modules". The app must boot with any subset (spec core B2).
    enabled_modules: str = ""
    rulepacks_dir: str = ""

    def enabled_module_names(self) -> list[str] | None:
        raw = self.enabled_modules.strip()
        if not raw:
            return None
        return [name.strip() for name in raw.split(",") if name.strip()]
