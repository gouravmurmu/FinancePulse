import time
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine | None:
    url = get_settings().database_url
    if not url:
        return None
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=2,
        pool_recycle=300,
        # Supabase's transaction pooler does not support prepared statements.
        connect_args={"prepare_threshold": None, "connect_timeout": 5},
    )


@lru_cache
def _session_factory() -> sessionmaker[Session] | None:
    engine = get_engine()
    return sessionmaker(engine, expire_on_commit=False) if engine else None


def get_session() -> Iterator[Session]:
    factory = _session_factory()
    if factory is None:
        from app.core.errors import AppError

        raise AppError("database_not_configured", "The database is not configured", 503)
    with factory() as session:
        yield session


def ping() -> tuple[str, float | None]:
    """Return ("ok" | "unavailable" | "not_configured", latency in ms)."""
    engine = get_engine()
    if engine is None:
        return "not_configured", None
    start = time.perf_counter()
    try:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
    except Exception:
        return "unavailable", None
    return "ok", round((time.perf_counter() - start) * 1000, 1)
