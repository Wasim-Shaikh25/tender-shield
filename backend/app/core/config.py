from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven settings. All variables use the TS_ prefix."""

    model_config = SettingsConfigDict(env_prefix="TS_", extra="ignore")

    env: str = "dev"

    # Public application URL (used for payment redirect callbacks, emails, etc.).
    app_url: str = ""

    # PostgreSQL 16 in all deployed environments; SQLite only for local tests.
    database_url: str = "sqlite:///./tendershield.db"

    # Uploaded-file storage root (LocalStorage in dev; S3 in prod, Doc §11.2).
    storage_dir: str = "./.tender_storage"
    storage_type: str = "local"  # "local" or "s3"
    s3_bucket: str = ""
    s3_region: str = ""
    s3_endpoint_url: str = ""
    s3_access_key_id: SecretStr | None = None
    s3_secret_access_key: SecretStr | None = None

    # OCR for scanned PDFs (offline RapidOCR). Off by default (loads ONNX models
    # + needs the `ocr` extra); when off, scanned docs are flagged needs_ocr.
    ocr_enabled: bool = False

    # Virus scanning (Doc §11.2). clamd socket path/address; when empty, scanning is
    # skipped and a warning is logged. Detected files are written to quarantine_dir.
    clamd_socket: str = ""  # e.g. /var/run/clamav/clamd.ctl or tcp://127.0.0.1:3310
    quarantine_dir: str = "./.tender_quarantine"

    # Auth (Doc §5). Keys are PEM strings; when absent an ephemeral RSA keypair
    # is generated at startup for dev/test only (never rely on it in prod).
    jwt_private_key: SecretStr | None = None
    jwt_public_key: SecretStr | None = None
    access_ttl_minutes: int = 15
    refresh_ttl_days: int = 30

    # CORS: comma-separated allowed origins for the browser SPA.
    # In dev "*" is tolerated; in prod it is rejected by the startup guard.
    cors_origins: str = "*"

    # Hosts allowed by TrustedHostMiddleware. "*" is allowed only in dev.
    allowed_hosts: str = "*"

    # Billing (Doc §7, §15). Webhook secret verifies the only billing truth.
    # No default is provided so that a missing secret fails production startup.
    razorpay_webhook_secret: SecretStr | None = None
    razorpay_key_id: str = ""
    razorpay_key_secret: SecretStr | None = None
    stripe_secret_key: SecretStr | None = None
    stripe_publishable_key: str = ""
    stripe_webhook_secret: SecretStr | None = None

    # Notifications (Doc §11.6/§11.7). SES/MSG91 are gated by credentials.
    email_from: str = ""
    ses_region: str = ""
    ses_access_key_id: SecretStr | None = None
    ses_secret_access_key: SecretStr | None = None
    msg91_auth_key: SecretStr | None = None
    msg91_sender_id: str = ""

    # LLM via OpenRouter (OpenAI-compatible API). No key → assistant free-form
    # answers and the risk LLM classifier are disabled, deterministic paths still run.
    openrouter_api_key: SecretStr | None = None
    openrouter_model: str = "openai/gpt-4o-mini"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_site_url: str = ""
    openrouter_app_name: str = "TenderShield"

    # Sign in with Apple (Doc §5). PEM private key may contain escaped newlines.
    apple_team_id: str = ""
    apple_services_id: str = ""
    apple_key_id: str = ""
    apple_private_key: SecretStr | None = None
    apple_redirect_uri: str = ""

    # Google OIDC (Doc §5). Client ID is enough for pure ID-token verification.
    google_client_id: str = ""
    google_client_secret: SecretStr | None = None
    google_redirect_uri: str = ""

    # Rate limiting / async task broker. Redis is required for distributed rate
    # limiting in multi-instance deployments; falls back to in-memory when empty.
    redis_url: str | None = None

    # Cookie policy for httpOnly refresh-token delivery. In production, Secure is
    # forced and SameSite is configurable ("lax" | "strict" | "none").
    cookie_name: str = "refresh_token"
    cookie_samesite: str = "lax"
    cookie_secure: bool | None = None  # None → Secure when env == "prod"

    # Comma-separated module names. Empty string means "discover everything
    # under app/modules". The app must boot with any subset (spec core B2).
    enabled_modules: str = ""
    rulepacks_dir: str = ""

    # Product flag: when True, paying workspaces may see unvalidated rule-patterns
    # with a clear disclaimer. False hides unvalidated patterns from paid plans.
    beta_unvalidated: bool = False

    # Observability. Sentry is initialized when a DSN is configured.
    sentry_dsn: SecretStr | None = None
    sentry_environment: str = ""
    sentry_traces_sample_rate: float = 0.0
    metrics_enabled: bool = True

    @field_validator("s3_secret_access_key", "apple_private_key", "sentry_dsn")
    @classmethod
    def _blank_secret_is_none(cls, v: SecretStr | None) -> SecretStr | None:
        if v is None:
            return None
        val = v.get_secret_value() if isinstance(v, SecretStr) else v
        return v if val else None

    @field_validator("cors_origins", "allowed_hosts")
    @classmethod
    def _strip_whitespace(cls, v: str) -> str:
        return v.strip()

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()] or ["*"]

    def allowed_host_list(self) -> list[str]:
        return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()] or ["*"]

    def cors_supports_credentials(self) -> bool:
        """Credentials can only be sent when origins are explicit (not '*')."""
        return "*" not in self.cors_origin_list()

    # Comma-separated module names. Empty string means "discover everything
    # under app/modules". The app must boot with any subset (spec core B2).
    def enabled_module_names(self) -> list[str] | None:
        raw = self.enabled_modules.strip()
        if not raw:
            return None
        return [name.strip() for name in raw.split(",") if name.strip()]

    def is_dev(self) -> bool:
        return self.env == "dev"

    def is_prod(self) -> bool:
        return self.env == "prod"

    def cookie_is_secure(self) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.is_prod()
