"""Annual fundamentals for US stocks from SEC EDGAR company facts.

    SEC_CONTACT_EMAIL=you@example.com python -m jobs.refresh_fundamentals

Runs weekly in GitHub Actions. Companies file 10-Ks once a year, so a weekly
refresh is enough. Requests are paced well under SEC's 10 per second limit.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import UTC, datetime

import httpx

from app.core.logging import configure_logging
from app.data.universe import UNIVERSE
from app.db.session import _session_factory
from app.providers import sec
from app.providers.base import ProviderError
from app.services import market_store

logger = logging.getLogger("jobs.refresh_fundamentals")
JOB = "refresh_fundamentals"


def run(only: list[str] | None, pause_s: float) -> int:
    if sec.user_agent() is None:
        logger.error("SEC_CONTACT_EMAIL is not set; SEC rejects requests without a contact")
        return 2
    factory = _session_factory()
    if factory is None:
        logger.error("DATABASE_URL is not set")
        return 2
    targets = [i for i in UNIVERSE if i.attributes.get("cik") and (not only or i.id in only)]
    retrieved_at = datetime.now(UTC)
    results: dict[str, dict[str, object]] = {}
    with factory() as session, httpx.Client() as client:
        job = market_store.start_job(session, JOB)
        for inst in targets:
            try:
                payload = sec.fetch_companyfacts(int(inst.attributes["cik"]), client)
                facts = sec.normalize_companyfacts(payload, inst.id, retrieved_at)
                n = market_store.upsert_fundamentals(session, facts)
                session.commit()
                results[inst.id] = {"rows": n}
                if n == 0:
                    results[inst.id]["warning"] = "no annual facts found"
                logger.info("fetched", extra={"instrument": inst.id, "rows": n})
            except (ProviderError, httpx.HTTPError, ValueError) as exc:
                session.rollback()
                results[inst.id] = {"error": str(exc)[:300]}
                logger.error("fetch_failed", extra={"instrument": inst.id, "error": str(exc)})
            time.sleep(pause_s)
        failed = [k for k, v in results.items() if "error" in v or "warning" in v]
        status = (
            "success" if not failed else ("failed" if len(failed) == len(results) else "partial")
        )
        market_store.finish_job(session, job, status, {"results": results, "failed": failed})
        logger.info("done", extra={"status": status, "failed": failed})
    return 0 if status != "failed" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*", help="limit to these instrument IDs")
    parser.add_argument("--pause", type=float, default=0.3, help="seconds between companies")
    args = parser.parse_args(argv)
    configure_logging("INFO")
    return run(args.only, args.pause)


if __name__ == "__main__":
    sys.exit(main())
