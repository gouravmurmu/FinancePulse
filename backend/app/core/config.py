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

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [o.strip().rstrip("/") for o in value.split(",") if o.strip()]
        return value

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
