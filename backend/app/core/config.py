from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Server-side configuration, read from environment variables only."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    version: str = "0.1.0"
    log_level: str = "INFO"

    # Postgres connection string. Optional so the API still boots and serves a
    # health check (reporting the database as not configured) without it.
    database_url: str | None = None

    # Comma-separated list of allowed browser origins.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )
    # Regex for extra allowed origins, e.g. Vercel preview deployments.
    cors_origin_regex: str | None = None

    request_timeout_seconds: float = 15.0

    # Supabase Auth. Access tokens are verified against the project's JWKS
    # (asymmetric signing keys); a legacy HS256 secret is accepted if set.
    supabase_url: str | None = None
    supabase_jwt_secret: str | None = None
    jwt_audience: str = "authenticated"

    # AI assistant: any OpenAI-compatible endpoint (Groq by default). Without a
    # key the assistant explains that AI is not configured; nothing else changes.
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = "llama-3.3-70b-versatile"
    # Budgets that keep usage inside the provider's free quota.
    ai_requests_per_user_day: int = 25
    ai_tokens_per_user_day: int = 40_000
    ai_tokens_per_day: int = 300_000

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [o.strip().rstrip("/") for o in value.split(",") if o.strip()]
        return value

    @field_validator("supabase_url")
    @classmethod
    def _strip_slash(cls, value: str | None) -> str | None:
        return value.rstrip("/") if value else None

    @field_validator("database_url")
    @classmethod
    def _normalize_driver(cls, value: str | None) -> str | None:
        # Supabase and Render hand out postgres:// URLs; SQLAlchemy needs the driver.
        if not value:
            return None
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix) :]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
