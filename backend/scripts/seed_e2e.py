"""Seed a throwaway database with synthetic prices for browser end-to-end tests.

Never point this at a real database: it writes made-up prices. It refuses to
run unless DATABASE_URL is a local host.
"""

from __future__ import annotations

import os
import sys
import uuid
import zlib
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import numpy as np
from alembic import command
from alembic.config import Config
from sqlalchemy import text

E2E_USER = uuid.UUID("11111111-1111-1111-1111-111111111111")
DAYS = 420


def main() -> None:
    url = os.environ.get("DATABASE_URL", "")
    if urlparse(url).hostname not in ("localhost", "127.0.0.1"):
        sys.exit("seed_e2e only runs against a local database")

    from app.data.universe import UNIVERSE
    from app.db.session import _session_factory
    from app.providers.base import Observation
    from app.services import market_store

    here = os.path.dirname(os.path.abspath(__file__))
    command.upgrade(Config(os.path.join(here, "..", "alembic.ini")), "head")
    today = datetime.now(UTC).date()
    days = [today - timedelta(days=i) for i in range(DAYS, 0, -1)]
    now = datetime.now(UTC)
    with _session_factory()() as s:
        s.execute(
            text(
                "insert into auth.users (id, email) values (:id, 'e2e@example.test') "
                "on conflict do nothing"
            ),
            {"id": E2E_USER},
        )
        market_store.sync_universe(s, UNIVERSE)
        obs = []
        for inst in UNIVERSE:
            rng = np.random.default_rng(zlib.crc32(inst.id.encode()))
            p = 83.0 if inst.asset_class == "fx" else float(rng.uniform(50, 3000))
            vol = {"crypto": 0.035, "fx": 0.003, "index": 0.01}.get(inst.asset_class, 0.016)
            for d in days:
                if inst.asset_class != "crypto" and d.weekday() >= 5:
                    continue
                p *= 1 + rng.normal(0.0004, vol)
                obs.append(
                    Observation(
                        instrument_id=inst.id,
                        provider="yfinance",
                        trading_date=d,
                        retrieved_at=now,
                        currency=inst.currency,
                        open=p * (1 + rng.normal(0, vol / 3)),
                        high=p * 1.01,
                        low=p * 0.99,
                        close=p,
                        adj_close=p,
                        volume=float(rng.integers(100_000, 10_000_000)),
                    )
                )
        market_store.upsert_observations(s, obs)
        run = market_store.start_job(s, "refresh_market_data")
        market_store.finish_job(s, run, "success", {"failed": []})
        s.commit()
    print(f"seeded {len(obs)} synthetic bars")


if __name__ == "__main__":
    main()
