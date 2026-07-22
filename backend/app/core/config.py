from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven settings. All variables use the TS_ prefix."""

    model_config = SettingsConfigDict(env_prefix="TS_", extra="ignore")

    env: str = "dev"
    # PostgreSQL 16 in all deployed environments; SQLite only for local tests.
    database_url: str = "sqlite:///./tendershield.db"
    # Comma-separated module names. Empty string means "discover everything
    # under app/modules". The app must boot with any subset (spec core B2).
    enabled_modules: str = ""
    rulepacks_dir: str = ""

    def enabled_module_names(self) -> list[str] | None:
        raw = self.enabled_modules.strip()
        if not raw:
            return None
        return [name.strip() for name in raw.split(",") if name.strip()]
