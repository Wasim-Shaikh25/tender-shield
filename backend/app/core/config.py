from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven settings. All variables use the TS_ prefix."""

    model_config = SettingsConfigDict(env_prefix="TS_", extra="ignore")

    env: str = "dev"
    # PostgreSQL 16 in all deployed environments; SQLite only for local tests.
    database_url: str = "sqlite:///./tendershield.db"

    # Auth (Doc §5). Keys are PEM strings; when absent an ephemeral RSA keypair
    # is generated at startup for dev/test only (never rely on it in prod).
    jwt_private_key: str = ""
    jwt_public_key: str = ""
    access_ttl_minutes: int = 15
    refresh_ttl_days: int = 30

    # CORS: comma-separated allowed origins for the browser SPA ("*" in dev).
    cors_origins: str = "*"

    # Billing (Doc §7, §15). Webhook secret verifies the only billing truth.
    razorpay_webhook_secret: str = "dev-razorpay-secret"

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
