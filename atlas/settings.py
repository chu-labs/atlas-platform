"""Runtime configuration. Everything comes from the environment; nothing is hardcoded."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "atlas-platform"
    environment: str = "local"
    log_level: str = "INFO"

    # Postgres
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "atlas"
    db_password: str = "atlas"
    db_name: str = "atlas"

    # Basic auth for every route except /health and /metrics. Empty user disables it.
    basic_auth_user: str = ""
    basic_auth_pass: str = ""

    # Production error queue and event bus. Empty means log only (local dev, tests).
    aws_region: str = "ap-southeast-2"
    queue_url_prod_errors: str = ""
    event_bus: str = ""

    # AI features
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"

    # Business timezone. Renewal dates are business dates in this zone.
    business_tz: str = "Australia/Sydney"

    @property
    def dsn(self) -> str:
        return f"host={self.db_host} port={self.db_port} user={self.db_user} password={self.db_password} dbname={self.db_name}"

    @property
    def admin_dsn(self) -> str:
        return f"host={self.db_host} port={self.db_port} user={self.db_user} password={self.db_password} dbname=postgres"


@lru_cache
def settings() -> Settings:
    return Settings()
