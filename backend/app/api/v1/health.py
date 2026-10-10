from datetime import UTC, datetime

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.db.session import ping
from app.schemas.health import DatabaseHealth, Health

router = APIRouter(tags=["health"])


@router.get("/health", response_model=Health, summary="Service and database health")
async def health() -> Health:
    settings = get_settings()
    db_status, latency = await run_in_threadpool(ping)
    # A database outage degrades the service but must not fail the health
    # check: stored-data endpoints report their own errors.
    return Health(
        status="ok" if db_status != "unavailable" else "degraded",
        version=settings.version,
        environment=settings.environment,
        server_time=datetime.now(UTC),
        database=DatabaseHealth(status=db_status, latency_ms=latency),
    )
