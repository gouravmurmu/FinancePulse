"""Refresh job against a real Postgres with providers stubbed out."""

import os
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, text

from app.providers.base import Observation, ProviderError

pytestmark = [
    pytest.mark.db,
    pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"),
]


@pytest.fixture
def db(monkeypatch):
    url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", url)
    from alembic import command
    from alembic.config import Config

    from app.core.config import get_settings
    from app.db.session import _session_factory, get_engine

    for f in (get_settings, get_engine, _session_factory):
        f.cache_clear()
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    command.upgrade(cfg, "head")
    eng = create_engine(url.replace("postgresql://", "postgresql+psycopg://", 1))
    with eng.begin() as c:
        c.execute(
            text("truncate market_observations, instrument_snapshots, job_runs, instrument_aliases")
        )
    yield eng
    eng.dispose()
    for f in (get_settings, get_engine, _session_factory):
        f.cache_clear()


def fake_history(inst, start, retrieved_at):
    if inst.id == "eq:us:TSLA":
        raise ProviderError("boom")
    days = [date(2026, 10, 6) + timedelta(days=i) for i in range(3)]
    return [
        Observation(
            instrument_id=inst.id,
            provider="yfinance",
            trading_date=d,
            retrieved_at=retrieved_at,
            currency=inst.currency,
            close=100.0 + i,
        )
        for i, d in enumerate(days)
    ]


def test_refresh_job_upserts_and_records_run(db, monkeypatch):
    from app.providers import coingecko, yahoo
    from jobs import refresh_market_data as job

    monkeypatch.setattr(yahoo, "fetch_history", fake_history)
    monkeypatch.setattr(coingecko, "fetch_markets", lambda insts, at: [])

    only = ["eq:us:AAPL", "eq:us:TSLA", "crypto:BTC"]
    assert job.run(backfill=True, years=1, only=only, pause_s=0) == 0
    # Running twice must not duplicate rows (idempotent upsert).
    assert job.run(backfill=False, years=1, only=only, pause_s=0) == 0

    with db.connect() as c:
        counts = dict(
            c.execute(
                text("select instrument_id, count(*) from market_observations group by 1")
            ).all()
        )
        assert counts == {"eq:us:AAPL": 3, "crypto:BTC": 3}
        n_instruments = c.execute(text("select count(*) from instruments where is_active")).scalar()
        assert n_instruments >= 50
        run = c.execute(text("select status, details from job_runs order by id desc limit 1")).one()
        assert run.status == "partial"
        assert run.details["failed"] == ["eq:us:TSLA"]
        assert "boom" in run.details["results"]["eq:us:TSLA"]["error"]
        # Search aliases were written.
        hit = c.execute(
            text("select instrument_id from instrument_aliases where lower(alias) = 'apple'")
        ).scalar()
        assert hit == "eq:us:AAPL"
