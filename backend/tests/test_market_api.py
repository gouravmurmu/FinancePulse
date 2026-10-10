"""Market API contract tests on a seeded Postgres (synthetic prices)."""

import os
from datetime import UTC, date, datetime, timedelta

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

pytestmark = [
    pytest.mark.db,
    pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"),
]

SEEDED = ["idx:us:SPX", "idx:in:NIFTY50", "eq:us:AAPL", "eq:in:TCS", "crypto:BTC",
          "metal:XAU:comex-fut", "metal:XAG:comex-fut", "fx:USDINR"]
START_PRICE = {"fx:USDINR": 83.0, "metal:XAU:comex-fut": 2000.0, "metal:XAG:comex-fut": 25.0}


def _bars(inst_id, days):
    rng = np.random.default_rng(abs(hash(inst_id)) % 2**32)
    price = START_PRICE.get(inst_id, 100.0)
    vol = 0.03 if inst_id.startswith("crypto") else 0.002 if inst_id.startswith("fx") else 0.01
    out = []
    for d in days:
        price *= 1 + rng.normal(0.0003, vol)
        out.append((d, price))
    return out


@pytest.fixture(scope="module")
def client():
    url = os.environ["TEST_DATABASE_URL"]
    os.environ["DATABASE_URL"] = url
    from alembic import command
    from alembic.config import Config

    from app.core.config import Settings, get_settings
    from app.data.universe import UNIVERSE
    from app.db.session import _session_factory, get_engine
    from app.main import create_app
    from app.services import cache, market_store

    for f in (get_settings, get_engine, _session_factory):
        f.cache_clear()
    cache.clear()
    command.upgrade(Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini")), "head")
    eng = create_engine(url.replace("postgresql://", "postgresql+psycopg://", 1))
    with eng.begin() as c:
        c.execute(text("truncate market_observations, instrument_snapshots, job_runs"))

    today = datetime.now(UTC).date()
    all_days = [today - timedelta(days=i) for i in range(800, 0, -1)]
    weekdays = [d for d in all_days if d.weekday() < 5]
    from app.providers.base import Observation

    with _session_factory()() as s:
        market_store.sync_universe(s, UNIVERSE)
        obs = []
        now = datetime.now(UTC)
        for inst_id in SEEDED:
            days = all_days if inst_id.startswith("crypto") else weekdays
            ccy = next(i.currency for i in UNIVERSE if i.id == inst_id)
            for d, p in _bars(inst_id, days):
                obs.append(Observation(
                    instrument_id=inst_id, provider="yfinance", trading_date=d, retrieved_at=now,
                    currency=ccy, close=p, open=p, high=p * 1.01, low=p * 0.99, adj_close=p,
                    volume=1000.0,
                ))
        market_store.upsert_observations(s, obs)
        run = market_store.start_job(s, "refresh_market_data")
        market_store.finish_job(s, run, "success", {"failed": []})
    yield TestClient(create_app(Settings()))
    for f in (get_settings, get_engine, _session_factory):
        f.cache_clear()
    cache.clear()
    eng.dispose()


def test_search_ranks_exact_alias_first(client):
    res = client.get("/api/v1/instruments", params={"q": "apple"})
    assert res.status_code == 200
    assert res.json()[0]["id"] == "eq:us:AAPL"
    assert client.get("/api/v1/instruments", params={"q": "nifty"}).json()[0]["id"].startswith(
        "idx:in:"
    )


def test_unknown_instrument_is_404_envelope(client):
    res = client.get("/api/v1/instruments/eq:us:NOPE")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "instrument_not_found"


def test_detail_has_quote_and_freshness(client):
    body = client.get("/api/v1/instruments/eq:us:AAPL").json()
    assert body["instrument"]["sector"] == "Technology"
    assert body["quote"]["price"] > 0
    assert body["quote"]["freshness"]["kind"] in ("eod", "delayed")
    assert body["snapshot"] is None


def test_detail_for_unseeded_instrument_is_unavailable_not_error(client):
    body = client.get("/api/v1/instruments/eq:us:MSFT").json()
    assert body["quote"]["price"] is None
    assert body["quote"]["freshness"]["kind"] == "unavailable"


def test_history_converts_usd_to_inr(client):
    usd = client.get("/api/v1/instruments/eq:us:AAPL/history", params={"period": "1M"}).json()
    inr = client.get(
        "/api/v1/instruments/eq:us:AAPL/history", params={"period": "1M", "currency": "INR"}
    ).json()
    assert usd["currency"] == "USD" and not usd["converted"]
    assert inr["currency"] == "INR" and inr["converted"]
    ratio = inr["bars"][-1]["close"] / usd["bars"][-1]["close"]
    assert 60 < ratio < 120  # around the seeded USD/INR level


def test_index_levels_are_never_converted(client):
    body = client.get(
        "/api/v1/instruments/idx:us:SPX/history", params={"period": "1M", "currency": "INR"}
    ).json()
    assert body["currency"] == "USD" and body["converted"] is False


def test_indicators_trimmed_to_period(client):
    body = client.get("/api/v1/instruments/eq:us:AAPL/indicators", params={"period": "3M"}).json()
    sma200 = body["series"]["sma_200"]
    assert sma200, "warm-up history should allow a 200-day SMA inside a 3M window"
    first = date.fromisoformat(sma200[0]["date"])
    assert first >= datetime.now(UTC).date() - timedelta(days=92)
    assert all(0 <= p["value"] <= 100 for p in body["series"]["rsi_14"])


def test_instrument_risk(client):
    body = client.get("/api/v1/instruments/crypto:BTC/risk", params={"period": "1Y"}).json()
    assert body["periods_per_year"] == 365
    assert body["metrics"]["volatility"] > 0
    assert body["metrics"]["var"] > 0
    assert body["metrics"]["expected_shortfall"] >= body["metrics"]["var"]
    assert body["metrics"]["max_drawdown"] <= 0
    assert body["risk_level"] in ("low", "moderate", "high")
    assert body["insight"].startswith("Bitcoin")


def test_overview(client):
    body = client.get(
        "/api/v1/markets/overview", params={"region": "global", "period": "1M"}
    ).json()
    ids = [q["instrument_id"] for q in body["indices"]]
    assert "idx:us:SPX" in ids
    assert body["comparison"]["series"][0]["points"][0]["value"] == pytest.approx(100)
    assert {m["session"] for m in body["markets"]} >= {"NYSE", "NSE", "CRYPTO"}
    assert body["data_status"]["status"] == "success"
    for q in body["gainers"]:
        assert q["change_pct"] > 0


def test_risk_lab_mixed_calendar(client):
    res = client.post(
        "/api/v1/risk/analyze",
        json={"instrument_ids": ["crypto:BTC", "idx:us:SPX", "metal:XAU:comex-fut"], "period": "1Y"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["periods_per_year"] == 252  # crypto sampled on exchange days
    m = body["correlation"]["matrix"]
    assert m[0][0] == pytest.approx(1.0)
    assert m[0][1] == pytest.approx(m[1][0])
    assert body["insight"]


def test_risk_lab_validation(client):
    res = client.post("/api/v1/risk/analyze", json={"instrument_ids": ["crypto:BTC"]})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"


def test_monte_carlo_reproducible(client):
    payload = {"weights": {"idx:us:SPX": 0.6, "metal:XAU:comex-fut": 0.4}, "horizon_days": 60,
               "paths": 500, "seed": 3, "lookback": "1Y"}
    a = client.post("/api/v1/risk/monte-carlo", json=payload).json()
    b = client.post("/api/v1/risk/monte-carlo", json=payload).json()
    assert a["percentiles"] == b["percentiles"]
    assert 0 <= a["probability_of_loss"] <= 1
    assert sum(h["count"] for h in a["histogram"]) == 500


def test_stress_preset(client):
    res = client.post(
        "/api/v1/risk/stress",
        json={"weights": {"idx:us:SPX": 50, "crypto:BTC": 30, "metal:XAU:comex-fut": 20},
              "preset": "equity_crash"},
    ).json()
    assert res["shocks"] == {"idx:us:SPX": -0.2, "crypto:BTC": -0.35, "metal:XAU:comex-fut": 0.05}
    assert res["total"] == pytest.approx(0.5 * -0.2 + 0.3 * -0.35 + 0.2 * 0.05)


def test_metal_context(client):
    body = client.get("/api/v1/instruments/metal:XAU:comex-fut", params={"period": "1Y"}).json()
    ctx = body["metal_context"]
    assert ctx["gold_silver_ratio"] > 0
    d = ctx["inr_decomposition"]
    assert d["inr_return"] == pytest.approx((1 + d["usd_return"]) * (1 + d["fx_return"]) - 1)
