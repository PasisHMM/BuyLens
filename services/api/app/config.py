from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"

    # Postgres. With Supabase, use the direct or *session* pooler URL; the transaction
    # pooler (port 6543) does not support the per-request `set local role` used for RLS.
    database_url: str = "postgresql://postgres:postgres@localhost:54322/postgres"
    db_pool_min: int = 1
    db_pool_max: int = 10

    # Supabase Auth. Tokens are verified with the project's JWKS (asymmetric signing keys).
    # Set SUPABASE_JWT_SECRET only for projects still on the legacy HS256 shared secret.
    supabase_url: str = "http://localhost:54321"
    supabase_jwt_secret: SecretStr | None = None
    jwt_audience: str = "authenticated"

    cors_origins: list[str] = ["http://localhost:3000"]

    # Redis: job queue (arq) and per-check progress streams.
    redis_url: str = "redis://localhost:6379/0"

    # LLM provider. Gemini is the default; model IDs change often, so they are config.
    llm_provider: Literal["gemini", "anthropic"] = "gemini"
    gemini_api_key: SecretStr | None = None
    gemini_fast_model: str = ""
    gemini_smart_model: str = ""
    anthropic_api_key: SecretStr | None = None
    anthropic_fast_model: str = "claude-haiku-5-5"
    anthropic_smart_model: str = "claude-sonnet-5-5"

    # Fetching seller pages.
    # Identify the bot honestly; add a contact URL or email in production.
    fetch_user_agent: str = "BuyLensBot/0.2 (shopping second-opinion; set FETCH_USER_AGENT with a contact)"
    fetch_timeout_s: float = 8.0
    fetch_max_bytes: int = 3_000_000
    fetch_min_interval_s: float = 1.0  # per domain
    listing_cache_ttl_s: int = 6 * 3600

    pipeline_version: str = "2026.10-p2"
    check_job_timeout_s: int = 90

    @property
    def jwt_issuer(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    @property
    def jwks_url(self) -> str:
        return f"{self.jwt_issuer}/.well-known/jwks.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
