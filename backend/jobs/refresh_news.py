"""Fetch recent headlines from Finnhub (needs FINNHUB_API_KEY).

    python -m jobs.refresh_news            # last 7 days for US stocks/ETFs + crypto feed

Stores headline, source, URL, time and summary only. Re-runs are idempotent.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import UTC, datetime, timedelta

import httpx

from app.core.logging import configure_logging
from app.data.universe import UNIVERSE, InstrumentDef
from app.db.session import _session_factory
from app.providers import finnhub
from app.providers.base import ProviderError
from app.services import market_store, news_service

logger = logging.getLogger("jobs.refresh_news")
JOB = "refresh_news"


def run(days: int, pause_s: float) -> int:
    factory = _session_factory()
    if factory is None:
        logger.error("DATABASE_URL is not set")
        return 2
    if not finnhub.api_key():
        logger.warning("FINNHUB_API_KEY is not set; skipping news")
        return 0
    now = datetime.now(UTC)
    start, end = (now - timedelta(days=days)).date(), now.date()
    results: dict[str, dict[str, object]] = {}
    with factory() as session, httpx.Client(timeout=20) as client:
        job = market_store.start_job(session, JOB)
        session.commit()
        batches: list[tuple[str, InstrumentDef | None]] = [
            (i.id, i) for i in UNIVERSE if finnhub.company_symbol(i)
        ]
        batches.append(("crypto-feed", None))
        for key, inst in batches:
            try:
                items = (
                    finnhub.fetch_company_news(client, inst, start, end)
                    if inst is not None
                    else finnhub.fetch_crypto_news(client, UNIVERSE)
                )
                new, links = news_service.store_items(session, items, now)
                session.commit()
                results[key] = {"fetched": len(items), "new": new, "links": links}
            except ProviderError as exc:
                session.rollback()
                results[key] = {"error": str(exc)[:300]}
                logger.error("news_failed", extra={"key": key, "error": str(exc)})
            time.sleep(pause_s)
        failed = [k for k, v in results.items() if "error" in v]
        status = (
            "success" if not failed else ("failed" if len(failed) == len(results) else "partial")
        )
        market_store.finish_job(session, job, status, {"results": results, "failed": failed})
        logger.info("done", extra={"status": status, "failed": failed})
    return 0 if status != "failed" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--pause", type=float, default=1.1, help="seconds between calls")
    args = parser.parse_args(argv)
    configure_logging("INFO")
    return run(args.days, args.pause)


if __name__ == "__main__":
    sys.exit(main())
