"""Baseline forecasts with walk-forward evaluation, once a day.

    python -m jobs.run_forecasts                 # all instruments
    python -m jobs.run_forecasts --only eq:us:AAPL

Results are upserted per instrument, horizon, as-of date and model version.
"""

from __future__ import annotations

import argparse
import logging
import sys

from app.core.logging import configure_logging
from app.db.session import _session_factory
from app.services import forecast_service, market_store
from app.services import market_data as md

logger = logging.getLogger("jobs.run_forecasts")
JOB = "run_forecasts"


def run(only: list[str] | None) -> int:
    factory = _session_factory()
    if factory is None:
        logger.error("DATABASE_URL is not set")
        return 2
    results: dict[str, object] = {}
    failed: list[str] = []
    with factory() as session:
        job = market_store.start_job(session, JOB)
        session.commit()
        for inst in md.list_instruments(session):
            if only and inst.id not in only:
                continue
            try:
                n = forecast_service.compute_and_store(session, inst)
                session.commit()
                results[inst.id] = {"horizons": n} if n else {"skipped": "not enough history"}
            except Exception as exc:  # noqa: BLE001 - one instrument never blocks the rest
                session.rollback()
                failed.append(inst.id)
                results[inst.id] = {"error": str(exc)[:300]}
                logger.exception("forecast_failed", extra={"instrument": inst.id})
        status = (
            "success" if not failed else ("failed" if len(failed) == len(results) else "partial")
        )
        market_store.finish_job(session, job, status, {"results": results, "failed": failed})
        logger.info("done", extra={"status": status, "failed": failed})
    return 0 if status != "failed" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*", help="limit to these instrument IDs")
    args = parser.parse_args(argv)
    configure_logging("INFO")
    return run(args.only)


if __name__ == "__main__":
    sys.exit(main())
