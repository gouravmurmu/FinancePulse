"""Forecast baselines: no look-ahead, honest baseline comparison, stored runs."""

import os
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from app.analytics import forecast as fc


def _walk(n=1100, drift=0.0, seed=1):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2021-01-01", periods=n)
    return pd.Series(100 * np.exp(np.cumsum(rng.normal(drift, 0.015, n))), index=idx)


def test_models_only_see_data_up_to_each_origin(monkeypatch):
    s = _walk()
    log = np.log(s.to_numpy())
    seen = []

    def spy(y, h):
        seen.append((len(y), float(y[-1]), h))
        return 0.01

    monkeypatch.setitem(fc.PREDICTORS, "drift", spy)
    results = fc.walk_forward(s, models=("naive", "drift"))
    assert seen and all(n == fc.TRAIN_WINDOW for n, _, _ in seen)
    # Every evaluation window ends where its target starts, never later.
    for r in results:
        h = r.horizon
        ends = [len(s) - 1 - h - fc.EVAL_STEP * k for k in range(fc.EVAL_ORIGINS)]
        allowed = {float(log[e]) for e in ends} | {float(log[-1])}
        assert {last for _, last, hh in seen if hh == h} <= allowed


def test_random_walk_does_not_beat_no_change():
    for seed in (1, 2):
        for r in fc.walk_forward(_walk(seed=seed)):
            assert r.best_model == "naive"
            assert not r.beats_baseline
            assert r.point == pytest.approx(r.last_close)
            assert r.lower < r.point < r.upper


def test_strong_trend_beats_no_change():
    r20 = next(r for r in fc.walk_forward(_walk(drift=0.003, seed=3)) if r.horizon == 20)
    assert r20.beats_baseline and r20.best_model in ("drift", "ets")
    assert r20.skill > 0.1
    assert r20.scores[r20.best_model].p_value < fc.SIGNIFICANCE
    assert r20.point > r20.last_close


def test_too_little_history_gives_nothing():
    assert fc.walk_forward(_walk(n=500)) == []


def test_dm_p_value():
    rng = np.random.default_rng(0)
    base = rng.normal(0, 1, 200)
    assert fc.dm_p_value(base, base, 0) is None
    assert fc.dm_p_value(base * 0.5, base, 0) < 0.01
    assert fc.dm_p_value(base * 2, base, 3) > 0.99


@pytest.mark.db
@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set")
def test_forecast_endpoint_serves_stored_runs():
    url = os.environ["TEST_DATABASE_URL"]
    os.environ["DATABASE_URL"] = url
    from alembic import command
    from alembic.config import Config
    from fastapi.testclient import TestClient
    from sqlalchemy import text

    from app.core.config import Settings, get_settings
    from app.data.universe import UNIVERSE
    from app.db.session import _session_factory, get_engine
    from app.main import create_app
    from app.providers.base import Observation
    from app.services import cache, market_store
    from jobs import run_forecasts

    for f in (get_settings, get_engine, _session_factory):
        f.cache_clear()
    cache.clear()
    command.upgrade(Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini")), "head")
    now = datetime.now(UTC)
    today = now.date()
    days = [today - timedelta(days=i) for i in range(1300, 0, -1)]
    with _session_factory()() as s:
        s.execute(text("truncate market_observations, forecast_runs, job_runs"))
        market_store.sync_universe(s, UNIVERSE)
        prices = np.exp(np.cumsum(np.random.default_rng(5).normal(0.0, 0.01, len(days)))) * 50
        market_store.upsert_observations(
            s,
            [
                Observation(
                    instrument_id="crypto:BTC",
                    provider="coingecko",
                    trading_date=d,
                    retrieved_at=now,
                    currency="USD",
                    close=float(p),
                    adj_close=float(p),
                )
                for d, p in zip(days, prices, strict=True)
            ],
        )
        s.commit()
    cache.clear()
    client = TestClient(create_app(Settings()))
    empty = client.get("/api/v1/instruments/eq:us:AAPL/forecast").json()
    assert empty["available"] is False and "unavailable" in empty["reason"]

    assert run_forecasts.run(["crypto:BTC", "eq:us:AAPL"]) == 0
    assert run_forecasts.run(["crypto:BTC"]) == 0  # re-run upserts, no duplicates
    body = client.get("/api/v1/instruments/crypto:BTC/forecast").json()
    assert body["available"] and not body["stale"]
    assert [h["horizon_days"] for h in body["horizons"]] == list(fc.HORIZONS)
    h5 = body["horizons"][0]
    assert h5["as_of"] == days[-1].isoformat()
    assert {m["model"] for m in h5["models"]} == set(fc.MODELS)
    assert h5["lower"] < h5["upper"]
    with _session_factory()() as s:
        assert s.execute(text("select count(*) from forecast_runs")).scalar_one() == 2
