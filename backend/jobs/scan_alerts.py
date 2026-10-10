"""Anomaly scan and alert evaluation. Runs right after the market data refresh.

    python -m jobs.scan_alerts                 # flag the last 14 days, evaluate rules
    python -m jobs.scan_alerts --since 2024-01-01   # re-scan a longer stretch

Flags are idempotent (one per instrument, day and kind), and each rule is
evaluated at most once per trading date, so re-running is safe.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, date, datetime, timedelta

from app.core.logging import configure_logging
from app.db.session import _session_factory
from app.services import alert_service as alerts
from app.services import market_data as md
from app.services import market_store

logger = logging.getLogger("jobs.scan_alerts")
JOB = "scan_alerts"
DEFAULT_LOOKBACK_DAYS = 14


def run(since: date | None) -> int:
    factory = _session_factory()
    if factory is None:
        logger.error("DATABASE_URL is not set")
        return 2
    today = datetime.now(UTC).date()
    since = since or today - timedelta(days=DEFAULT_LOOKBACK_DAYS)
    results: dict[str, object] = {}
    errors: list[str] = []

    with factory() as session:
        job = market_store.start_job(session, JOB)
        session.commit()
        flagged = 0
        for inst in md.list_instruments(session):
            try:
                found = alerts.scan_instrument(session, inst, since, today)
                flagged += alerts.store_anomalies(session, inst.id, found)
                session.commit()
            except Exception as exc:  # noqa: BLE001 - one instrument never blocks the rest
                session.rollback()
                errors.append(inst.id)
                logger.exception("scan_failed", extra={"instrument": inst.id})
                results[inst.id] = {"error": str(exc)[:300]}
        results["anomalies_added"] = flagged

        try:
            results["alerts"] = alerts.evaluate_rules(session)
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            errors.append("alerts")
            logger.exception("evaluate_failed")
            results["alerts"] = {"error": str(exc)[:300]}

        status = "success" if not errors else "partial"
        market_store.finish_job(
            session, job, status, {"since": since.isoformat(), "results": results, "failed": errors}
        )
        logger.info("done", extra={"status": status, "anomalies_added": flagged})
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", type=date.fromisoformat, help="flag anomalies from this date")
    args = parser.parse_args(argv)
    configure_logging("INFO")
    return run(args.since)


if __name__ == "__main__":
    sys.exit(main())
