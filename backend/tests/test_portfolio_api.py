"""Portfolio and watchlist API on a seeded Postgres: P&L, FX, isolation, CSV."""

import os
import time
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

pytestmark = [
    pytest.mark.db,
    pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"),
]

SECRET = "portfolio-test-secret-at-least-32-bytes"  # noqa: S105 (test-only key)
USER_A = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
USER_B = uuid.UUID("00000000-0000-0000-0000-0000000000b1")
# Flat prices make P&L exact; random walks give the risk maths something to chew.
FLAT = {"eq:us:AAPL": 150.0, "eq:in:TCS": 3000.0, "fx:USDINR": 80.0, "metal:XAU:comex-fut": 2000.0}
WALK = ["crypto:BTC", "idx:us:SPX", "idx:in:NIFTY50", "eq:us:MSFT"]


def token(user):
    return jwt.encode(
        {
            "sub": str(user),
            "aud": "authenticated",
            "role": "authenticated",
            "exp": int(time.time()) + 600,
        },
        SECRET,
        algorithm="HS256",
    )


def auth(user=USER_A):
    return {"Authorization": f"Bearer {token(user)}"}


@pytest.fixture(scope="module")
def client():
    url = os.environ["TEST_DATABASE_URL"]
    os.environ["DATABASE_URL"] = url
    os.environ["SUPABASE_JWT_SECRET"] = SECRET
    os.environ.pop("SUPABASE_URL", None)
    from alembic import command
    from alembic.config import Config

    from app.core.config import Settings, get_settings
    from app.data.universe import UNIVERSE
    from app.db.session import _session_factory, get_engine
    from app.main import create_app
    from app.providers.base import Observation
    from app.services import cache, market_store

    for f in (get_settings, get_engine, _session_factory):
        f.cache_clear()
    cache.clear()
    command.upgrade(Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini")), "head")
    eng = create_engine(url.replace("postgresql://", "postgresql+psycopg://", 1))
    with eng.begin() as c:
        c.execute(text("truncate market_observations, instrument_snapshots, job_runs"))
        c.execute(text("delete from portfolios; delete from watchlists"))
        c.execute(text("delete from auth.users where id in (:a, :b)"), {"a": USER_A, "b": USER_B})
        c.execute(
            text("insert into auth.users (id, email) values (:a, 'pa@x.test'), (:b, 'pb@x.test')"),
            {"a": USER_A, "b": USER_B},
        )

    today = datetime.now(UTC).date()
    days = [today - timedelta(days=i) for i in range(500, 0, -1)]
    weekdays = [d for d in days if d.weekday() < 5]
    now = datetime.now(UTC)
    with _session_factory()() as s:
        market_store.sync_universe(s, UNIVERSE)
        obs = []
        for inst_id in list(FLAT) + WALK:
            rng = np.random.default_rng(len(inst_id))
            ccy = next(i.currency for i in UNIVERSE if i.id == inst_id)
            price = FLAT.get(inst_id, 100.0)
            for d in days if inst_id.startswith("crypto") else weekdays:
                if inst_id in WALK:
                    price *= 1 + rng.normal(0.0005, 0.02)
                obs.append(
                    Observation(
                        instrument_id=inst_id,
                        provider="yfinance",
                        trading_date=d,
                        retrieved_at=now,
                        currency=ccy,
                        close=price,
                        adj_close=price,
                    )
                )
        market_store.upsert_observations(s, obs)
        s.commit()
    yield TestClient(create_app(Settings()))
    os.environ.pop("SUPABASE_JWT_SECRET", None)
    for f in (get_settings, get_engine, _session_factory):
        f.cache_clear()
    cache.clear()
    eng.dispose()


def _days_ago(n):
    d = datetime.now(UTC).date() - timedelta(days=n)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.isoformat()


def _portfolio(client, name, base="USD", user=USER_A):
    res = client.post(
        "/api/v1/portfolios", json={"name": name, "base_currency": base}, headers=auth(user)
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _tx(client, pid, user=USER_A, **kw):
    body = {"side": "buy", "trade_date": _days_ago(200), "unit": "unit", "fees": 0, **kw}
    return client.post(f"/api/v1/portfolios/{pid}/transactions", json=body, headers=auth(user))


def test_requires_sign_in(client):
    assert client.get("/api/v1/portfolios").status_code == 401
    bad = {"Authorization": "Bearer not-a-jwt"}
    assert client.get("/api/v1/portfolios", headers=bad).status_code == 401


def test_pnl_with_weighted_average_cost(client):
    pid = _portfolio(client, "Exact")
    assert (
        _tx(client, pid, instrument_id="eq:us:AAPL", quantity=10, price=100, fees=5).status_code
        == 201
    )
    assert (
        _tx(client, pid, instrument_id="eq:us:AAPL", quantity=10, price=120, fees=5).status_code
        == 201
    )
    r = _tx(
        client,
        pid,
        instrument_id="eq:us:AAPL",
        side="sell",
        quantity=5,
        price=130,
        fees=2,
        trade_date=_days_ago(100),
    )
    assert r.status_code == 201
    s = client.get(f"/api/v1/portfolios/{pid}/summary", headers=auth()).json()
    (h,) = s["holdings"]
    assert h["quantity"] == pytest.approx(15)
    assert h["average_cost"] == pytest.approx(110.5)
    assert h["price"] == pytest.approx(150)
    assert h["value_base"] == pytest.approx(2250)
    assert h["unrealized_base"] == pytest.approx(2250 - 1657.5)
    assert s["totals"]["realized"] == pytest.approx(95.5)
    assert s["totals"]["fees"] == pytest.approx(12)
    assert s["allocation"]["asset_class"][0] == {"label": "Stocks", "value": 2250.0, "weight": 1.0}
    assert h["freshness"]["kind"] in ("eod", "delayed")


def test_inr_portfolio_converts_usd_holdings(client):
    pid = _portfolio(client, "Rupee", base="INR")
    _tx(client, pid, instrument_id="eq:us:AAPL", quantity=2, price=150)
    _tx(client, pid, instrument_id="eq:in:TCS", quantity=1, price=3000)
    s = client.get(f"/api/v1/portfolios/{pid}/summary", headers=auth()).json()
    t = s["totals"]
    # 2 * 150 USD * 80 + 3000 INR, all bought at today's prices and rate
    assert t["value"] == pytest.approx(27_000)
    assert t["unrealized"] == pytest.approx(0)
    assert t["fx_effect"] == pytest.approx(0)
    assert {a["label"] for a in s["allocation"]["currency"]} == {"USD", "INR"}


def test_cannot_sell_more_than_held(client):
    pid = _portfolio(client, "Oversell")
    _tx(client, pid, instrument_id="eq:us:AAPL", quantity=1, price=100)
    r = _tx(client, pid, instrument_id="eq:us:AAPL", side="sell", quantity=2, price=100)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "oversold"
    txs = client.get(f"/api/v1/portfolios/{pid}/transactions", headers=auth()).json()
    assert len(txs) == 1  # the bad sale was rolled back


def test_deleting_a_buy_that_a_sale_depends_on_is_refused(client):
    pid = _portfolio(client, "Dependent")
    buy = _tx(client, pid, instrument_id="eq:us:AAPL", quantity=1, price=100).json()
    _tx(
        client,
        pid,
        instrument_id="eq:us:AAPL",
        side="sell",
        quantity=1,
        price=110,
        trade_date=_days_ago(10),
    )
    r = client.delete(f"/api/v1/portfolios/{pid}/transactions/{buy['id']}", headers=auth())
    assert r.status_code == 422


def test_indices_cannot_be_held_and_metal_needs_weight(client):
    pid = _portfolio(client, "Rules")
    r = _tx(client, pid, instrument_id="idx:us:SPX", quantity=1, price=1)
    assert r.json()["error"]["code"] == "not_holdable"
    r = _tx(client, pid, instrument_id="metal:XAU:comex-fut", quantity=1, price=2000)
    assert r.json()["error"]["code"] == "invalid_unit"
    r = _tx(
        client,
        pid,
        instrument_id="metal:XAU:comex-fut",
        quantity=31.1034768,
        unit="gram",
        price=round(2000 / 31.1034768, 8),
    )
    assert r.status_code == 201
    (h,) = client.get(f"/api/v1/portfolios/{pid}/summary", headers=auth()).json()["holdings"]
    assert h["unit"] == "gram"
    assert h["value_base"] == pytest.approx(2000)
    assert h["unrealized_base"] == pytest.approx(0, abs=0.01)
    assert h["price"] == pytest.approx(2000 / 31.1034768, rel=1e-6)


def test_future_dates_and_bad_numbers_are_rejected(client):
    pid = _portfolio(client, "Validation")
    future = (datetime.now(UTC).date() + timedelta(days=3)).isoformat()
    assert (
        _tx(
            client, pid, instrument_id="eq:us:AAPL", quantity=1, price=1, trade_date=future
        ).status_code
        == 422
    )
    assert _tx(client, pid, instrument_id="eq:us:AAPL", quantity=0, price=1).status_code == 422
    assert _tx(client, pid, instrument_id="eq:us:AAPL", quantity=1, price=-1).status_code == 422


def test_users_cannot_see_or_change_each_others_portfolios(client):
    pid = _portfolio(client, "Private")
    tx = _tx(client, pid, instrument_id="eq:us:AAPL", quantity=1, price=100).json()
    hb = auth(USER_B)
    assert pid not in [p["id"] for p in client.get("/api/v1/portfolios", headers=hb).json()]
    for method, path in [
        ("get", f"/api/v1/portfolios/{pid}/summary"),
        ("get", f"/api/v1/portfolios/{pid}/transactions"),
        ("get", f"/api/v1/portfolios/{pid}/transactions.csv"),
        ("delete", f"/api/v1/portfolios/{pid}"),
        ("delete", f"/api/v1/portfolios/{pid}/transactions/{tx['id']}"),
    ]:
        assert getattr(client, method)(path, headers=hb).status_code == 404, path
    r = client.patch(f"/api/v1/portfolios/{pid}", json={"name": "pwned"}, headers=hb)
    assert r.status_code == 404
    r = _tx(client, pid, user=USER_B, instrument_id="eq:us:AAPL", quantity=1, price=1)
    assert r.status_code == 404
    # Still intact for the owner.
    assert len(client.get(f"/api/v1/portfolios/{pid}/transactions", headers=auth()).json()) == 1


def test_duplicate_names_conflict(client):
    _portfolio(client, "Twice")
    r = client.post("/api/v1/portfolios", json={"name": "Twice"}, headers=auth())
    assert r.status_code == 409
    # Another user may use the same name.
    _portfolio(client, "Twice", user=USER_B)


def test_csv_round_trip_and_all_or_nothing_import(client):
    src = _portfolio(client, "Export")
    _tx(client, src, instrument_id="eq:us:AAPL", quantity=3, price=101.5, fees=1, notes="first")
    _tx(client, src, instrument_id="crypto:BTC", quantity=0.25, price=40000)
    csv_text = client.get(f"/api/v1/portfolios/{src}/transactions.csv", headers=auth()).text
    assert (
        csv_text.splitlines()[0]
        == "date,instrument_id,side,quantity,unit,price,fees,notes,currency"
    )

    dst = _portfolio(client, "Import")
    dry = client.post(
        f"/api/v1/portfolios/{dst}/import", json={"csv": csv_text, "dry_run": True}, headers=auth()
    )
    assert dry.json() == {"status": "ok", "rows": 2, "dry_run": True}
    assert client.get(f"/api/v1/portfolios/{dst}/transactions", headers=auth()).json() == []
    ok = client.post(f"/api/v1/portfolios/{dst}/import", json={"csv": csv_text}, headers=auth())
    assert ok.json()["rows"] == 2
    assert client.get(f"/api/v1/portfolios/{dst}/transactions.csv", headers=auth()).text == csv_text

    bad = csv_text + "2026-01-01,eq:us:NOPE,buy,1,unit,1,0,,USD\n"
    r = client.post(f"/api/v1/portfolios/{dst}/import", json={"csv": bad}, headers=auth())
    assert r.status_code == 422
    assert "unknown instrument" in r.json()["error"]["details"][0]
    assert len(client.get(f"/api/v1/portfolios/{dst}/transactions", headers=auth()).json()) == 2


def test_performance_risk_and_stress(client):
    pid = _portfolio(client, "Perf")
    _tx(client, pid, instrument_id="crypto:BTC", quantity=1, price=100, trade_date=_days_ago(400))
    _tx(client, pid, instrument_id="eq:us:MSFT", quantity=10, price=100, trade_date=_days_ago(400))
    _tx(client, pid, instrument_id="eq:us:AAPL", quantity=5, price=150, trade_date=_days_ago(300))
    perf = client.get(
        f"/api/v1/portfolios/{pid}/performance", params={"period": "1Y"}, headers=auth()
    ).json()
    assert perf["portfolio"][0]["value"] == 100
    assert perf["benchmark"]["instrument_id"] == "idx:us:SPX"
    assert perf["metrics"]["volatility"] > 0
    assert perf["periods_per_year"] == 252
    rc = [r["risk_contribution"] for r in perf["risk"]]
    assert sum(rc) == pytest.approx(1, abs=1e-4)
    # AAPL is flat, so it adds no variance.
    aapl = next(r for r in perf["risk"] if r["instrument_id"] == "eq:us:AAPL")
    assert aapl["risk_contribution"] == pytest.approx(0, abs=1e-6)
    assert len(perf["correlation"]["ids"]) == 3

    st = client.post(
        f"/api/v1/portfolios/{pid}/stress",
        json={"shocks": {"crypto:BTC": -0.5, "eq:us:MSFT": 0, "eq:us:AAPL": 0}},
        headers=auth(),
    ).json()
    s = client.get(f"/api/v1/portfolios/{pid}/summary", headers=auth()).json()
    btc = next(h for h in s["holdings"] if h["instrument_id"] == "crypto:BTC")
    assert st["pnl"] == pytest.approx(-0.5 * btc["value_base"], abs=0.01)


def test_twr_matches_single_asset_return(client):
    pid = _portfolio(client, "Single")
    _tx(client, pid, instrument_id="eq:us:MSFT", quantity=1, price=1, trade_date=_days_ago(450))
    _tx(client, pid, instrument_id="eq:us:MSFT", quantity=0.5, price=1, trade_date=_days_ago(400))
    perf = client.get(
        f"/api/v1/portfolios/{pid}/performance", params={"period": "1Y"}, headers=auth()
    ).json()
    pts = perf["portfolio"]
    # Within the window there are no flows, so TWR equals MSFT's own price change.
    bars = client.get("/api/v1/instruments/eq:us:MSFT/history", params={"period": "MAX"}).json()
    closes = {b["date"]: b["close"] for b in bars["bars"]}
    first_day = perf["start"]
    prev = max(d for d in closes if d < first_day)
    assert perf["metrics"]["time_weighted_return"] == pytest.approx(
        closes[max(closes)] / closes[prev] - 1, rel=1e-6
    )
    assert pts[-1]["value"] == pytest.approx(100 * closes[max(closes)] / closes[prev], rel=1e-4)


def test_watchlists_are_private_and_quote_items(client):
    w = client.post("/api/v1/watchlists", json={"name": "Tech"}, headers=auth()).json()
    client.post(
        f"/api/v1/watchlists/{w['id']}/items", json={"instrument_id": "eq:us:AAPL"}, headers=auth()
    )
    client.post(
        f"/api/v1/watchlists/{w['id']}/items", json={"instrument_id": "eq:us:AAPL"}, headers=auth()
    )
    full = client.get(f"/api/v1/watchlists/{w['id']}", headers=auth()).json()
    assert full["instrument_ids"] == ["eq:us:AAPL"]
    assert full["quotes"][0]["price"] == pytest.approx(150)
    assert client.get(f"/api/v1/watchlists/{w['id']}", headers=auth(USER_B)).status_code == 404
    r = client.post(
        f"/api/v1/watchlists/{w['id']}/items",
        json={"instrument_id": "eq:us:MSFT"},
        headers=auth(USER_B),
    )
    assert r.status_code == 404
    client.delete(f"/api/v1/watchlists/{w['id']}/items/eq:us:AAPL", headers=auth())
    assert (
        client.get(f"/api/v1/watchlists/{w['id']}", headers=auth()).json()["instrument_ids"] == []
    )


def test_me_returns_defaults(client):
    body = client.get("/api/v1/me", headers=auth()).json()
    assert body["user_id"] == str(USER_A)
    assert body["base_currency"] == "USD"
