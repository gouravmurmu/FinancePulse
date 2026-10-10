"""Daily market data refresh. Runs in GitHub Actions (see .github/workflows).

    python -m jobs.refresh_market_data              # incremental (last ~10 days)
    python -m jobs.refresh_market_data --backfill   # full history (default 5 years)

Each instrument is fetched independently; one failure never blocks the rest.
The run is recorded in job_runs with per-instrument results.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.logging import configure_logging
from app.data.universe import UNIVERSE, InstrumentDef
from app.db.session import _session_factory
from app.providers import coingecko, yahoo
from app.providers.base import ProviderError
from app.services import market_store

logger = logging.getLogger("jobs.refresh_market_data")
JOB = "refresh_market_data"
# Re-fetch a few days on every run so late corrections and the in-progress
# bar get overwritten by final values.
OVERLAP_DAYS = 10


def start_date(session: Session, inst: InstrumentDef, backfill_years: int, backfill: bool) -> date:
    floor = date.today() - timedelta(days=round(365.25 * backfill_years))
    if backfill:
        return floor
    latest = market_store.latest_trading_date(session, inst.id)
    if latest is None:
        return floor
    return max(floor, latest.date() - timedelta(days=OVERLAP_DAYS))


def run(backfill: bool, years: int, only: list[str] | None, pause_s: float) -> int:
    factory = _session_factory()
    if factory is None:
        logger.error("DATABASE_URL is not set")
        return 2
    instruments = [i for i in UNIVERSE if not only or i.id in only]
    retrieved_at = datetime.now(UTC)
    results: dict[str, dict[str, object]] = {}

    with factory() as session:
        job = market_store.start_job(session, JOB)
        market_store.sync_universe(session, UNIVERSE)
        session.commit()

        for inst in instruments:
            if yahoo.PROVIDER not in inst.aliases:
                continue
            start = start_date(session, inst, years, backfill)
            try:
                obs = yahoo.fetch_history(inst, start, retrieved_at)
                n = market_store.upsert_observations(session, obs)
                session.commit()
                suspect = sum(1 for o in obs if o.quality_status == "suspect")
                results[inst.id] = {"rows": n, "from": start.isoformat(), "suspect": suspect}
                if n == 0:
                    results[inst.id]["warning"] = "no data returned"
                logger.info("fetched", extra={"instrument": inst.id, "rows": n})
            except ProviderError as exc:
                session.rollback()
                results[inst.id] = {"error": str(exc)[:300]}
                logger.error("fetch_failed", extra={"instrument": inst.id, "error": str(exc)})
            time.sleep(pause_s)

        crypto = [i for i in instruments if coingecko.PROVIDER in i.aliases]
        try:
            snaps = coingecko.fetch_markets(crypto, retrieved_at)
            results["coingecko:markets"] = {"rows": market_store.upsert_snapshots(session, snaps)}
            session.commit()
        except ProviderError as exc:
            session.rollback()
            results["coingecko:markets"] = {"error": str(exc)[:300]}

        failed = [k for k, v in results.items() if "error" in v or "warning" in v]
        status = (
            "success" if not failed else ("failed" if len(failed) == len(results) else "partial")
        )
        market_store.finish_job(
            session,
            job,
            status,
            {"backfill": backfill, "results": results, "failed": failed},
        )
        logger.info("done", extra={"status": status, "failed": failed})
    return 0 if status != "failed" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backfill", action="store_true", help="refetch full history")
    parser.add_argument("--years", type=int, default=5, help="history depth for backfill")
    parser.add_argument("--only", nargs="*", help="limit to these instrument IDs")
    parser.add_argument("--pause", type=float, default=0.5, help="seconds between symbols")
    args = parser.parse_args(argv)
    configure_logging("INFO")
    return run(args.backfill, args.years, args.only, args.pause)


if __name__ == "__main__":
    sys.exit(main())
