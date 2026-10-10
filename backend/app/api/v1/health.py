from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.deps import DbSession
from app.core.config import get_settings
from app.db.session import ping
from app.schemas.health import DatabaseHealth, Health
from app.services import market_data as md

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


# How often each scheduled job should succeed; overdue means it missed at
# least one run. Optional jobs do nothing until their API key is configured.
JOB_SCHEDULE: dict[str, tuple[float, bool]] = {
    "refresh_market_data": (18, False),
    "scan_alerts": (18, False),
    "run_forecasts": (30, False),
    "refresh_news": (18, True),
    "score_sentiment": (18, True),
    "refresh_fundamentals": (8 * 24, True),
}


def _job_status(session: Session) -> dict[str, Any]:
    now = datetime.now(UTC)
    jobs = []
    for job, (hours, optional) in JOB_SCHEDULE.items():
        run = md.last_job_run(session, job)
        ok_at = run["last_success_at"] if run else None
        overdue = ok_at is None or now - ok_at > timedelta(hours=hours)
        jobs.append(
            {
                "job": job,
                "last_status": run["status"] if run else None,
                "last_success_at": ok_at,
                "expected_every_hours": hours,
                "optional": optional,
                "overdue": overdue,
            }
        )
    attention = any(j["overdue"] and not j["optional"] for j in jobs)
    return {"status": "attention" if attention else "ok", "checked_at": now, "jobs": jobs}


@router.get("/status", summary="Freshness of the scheduled data jobs (for monitoring)")
def job_status(session: DbSession) -> dict[str, Any]:
    return _job_status(session)
