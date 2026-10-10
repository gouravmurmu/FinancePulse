"""Anomaly scan and alert rules on a seeded Postgres: flags, firing, isolation."""

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

SECRET = "alerts-test-secret-at-least-32-bytes-long"  # noqa: S105 (test-only key)
USER_A = uuid.UUID("00000000-0000-0000-0000-0000000000a2")
USER_B = uuid.UUID("00000000-0000-0000-0000-0000000000b2")
JUMP = 0.25  # AAPL's last close is 25% above the day before


def auth(user=USER_A):
    claims = {
        "sub": str(user),
        "aud": "authenticated",
        "role": "authenticated",
        "exp": int(time.time()) + 600,
    }
    return {"Authorization": f"Bearer {jwt.encode(claims, SECRET, algorithm='HS256')}"}


@pytest.fixture(scope="module")
def env():
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
        c.execute(text("truncate market_observations, instrument_snapshots, job_runs, anomalies"))
        c.execute(text("delete from alert_rules"))
        c.execute(text("delete from auth.users where id in (:a, :b)"), {"a": USER_A, "b": USER_B})
        c.execute(
            text("insert into auth.users (id, email) values (:a, 'aa@x.test'), (:b, 'ab@x.test')"),
            {"a": USER_A, "b": USER_B},
        )

    today = datetime.now(UTC).date()
    weekdays = [
        d for d in (today - timedelta(days=i) for i in range(700, 0, -1)) if d.weekday() < 5
    ]
    now = datetime.now(UTC)
    with _session_factory()() as s:
        market_store.sync_universe(s, UNIVERSE)
        obs = []
        for inst_id, seed in (("eq:us:AAPL", 1), ("idx:us:SPX", 2), ("eq:in:TCS", 3)):
            rng = np.random.default_rng(seed)
            ccy = next(i.currency for i in UNIVERSE if i.id == inst_id)
            price = 3000.0 if inst_id == "eq:in:TCS" else 100.0
            for n, d in enumerate(weekdays):
                if inst_id != "eq:in:TCS":
                    price *= 1 + rng.normal(0.0003, 0.01)
                if inst_id == "eq:us:AAPL" and n == len(weekdays) - 1:
                    price *= 1 + JUMP
                obs.append(
                    Observation(
                        instrument_id=inst_id,
                        provider="yfinance",
                        trading_date=d,
                        retrieved_at=now,
                        currency=ccy,
                        close=price,
                        adj_close=price,
                        volume=1_000_000 * (8 if n == len(weekdays) - 1 else 1 + rng.random()),
                    )
                )
        market_store.upsert_observations(s, obs)
        s.commit()
    cache.clear()
    yield {"client": TestClient(create_app(Settings())), "eng": eng, "last": weekdays[-1]}
    os.environ.pop("SUPABASE_JWT_SECRET", None)
    for f in (get_settings, get_engine, _session_factory):
        f.cache_clear()
    cache.clear()
    eng.dispose()


def run_job(env):
    from app.services import cache
    from jobs import scan_alerts

    cache.clear()
    assert scan_alerts.run(None) == 0
    with env["eng"].connect() as c:
        return c.execute(
            text("select details from job_runs where job = 'scan_alerts' order by started_at desc")
        ).scalar()


def test_rules_need_sign_in(env):
    assert env["client"].get("/api/v1/alerts/rules").status_code == 401


def test_rule_validation(env):
    c = env["client"]
    r = c.post(
        "/api/v1/alerts/rules",
        headers=auth(),
        json={"instrument_id": "eq:us:AAPL", "kind": "price_above"},
    )
    assert r.status_code == 422
    r = c.post(
        "/api/v1/alerts/rules",
        headers=auth(),
        json={"instrument_id": "eq:us:AAPL", "kind": "move_pct", "threshold": 3},
    )
    assert r.status_code == 422
    r = c.post(
        "/api/v1/alerts/rules",
        headers=auth(),
        json={"instrument_id": "nope:X", "kind": "anomaly"},
    )
    assert r.status_code == 404


def test_scan_flags_and_rules_fire_once(env):
    c = env["client"]
    rules = [
        {"instrument_id": "eq:us:AAPL", "kind": "anomaly"},
        {"instrument_id": "eq:us:AAPL", "kind": "move_pct", "threshold": 0.1},
        {"instrument_id": "eq:in:TCS", "kind": "price_above", "threshold": 2500},
        {"instrument_id": "eq:in:TCS", "kind": "price_below", "threshold": 2500},
    ]
    ids = []
    for body in rules:
        r = c.post("/api/v1/alerts/rules", headers=auth(), json=body)
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
    # User B's rule on the same instrument stays theirs.
    r = c.post(
        "/api/v1/alerts/rules",
        headers=auth(USER_B),
        json={"instrument_id": "eq:us:AAPL", "kind": "anomaly"},
    )
    assert r.status_code == 201

    first_run = run_job(env)

    flags = c.get("/api/v1/anomalies", params={"instrument_id": "eq:us:AAPL"}).json()
    kinds = {f["kind"] for f in flags if f["observed_at"] == env["last"].isoformat()}
    assert {"return", "volume"} <= kinds
    ret = next(f for f in flags if f["kind"] == "return")
    assert ret["zscore"] > 4 and ret["description"].startswith("Moved +2")
    # A flat price never moves, so only its volume spike is flagged.
    tcs = c.get("/api/v1/anomalies", params={"instrument_id": "eq:in:TCS"}).json()
    assert [f["kind"] for f in tcs] == ["volume"]

    ev = c.get("/api/v1/alerts/events", headers=auth()).json()
    fired = {e["rule_id"] for e in ev["events"]}
    assert fired == {ids[0], ids[1], ids[2]}  # price_below is not met
    assert ev["unread"] == 3
    msg = next(e["message"] for e in ev["events"] if e["rule_id"] == ids[2])
    assert "₹3,000.00" in msg and "above" in msg

    listed = {r["id"]: r for r in c.get("/api/v1/alerts/rules", headers=auth()).json()}
    assert listed[ids[2]]["condition_met"] is True
    assert listed[ids[3]]["condition_met"] is False

    assert first_run["results"]["anomalies_added"] >= 4
    assert first_run["results"]["alerts"]["fired"] == 4  # 3 for A, 1 for B
    # Re-running on the same data adds and fires nothing new.
    again = run_job(env)
    assert again["results"]["anomalies_added"] == 0
    assert again["results"]["alerts"]["fired"] == 0
    assert c.get("/api/v1/alerts/events", headers=auth()).json()["unread"] == 3
    assert c.get("/api/v1/alerts/events", headers=auth(USER_B)).json()["unread"] == 1

    # Marking read is per user.
    first = ev["events"][0]["id"]
    r = c.post("/api/v1/alerts/events/read", headers=auth(), json={"ids": [first]})
    assert r.json() == {"updated": 1}
    r = c.post("/api/v1/alerts/events/read", headers=auth(USER_B), json={"ids": [first]})
    assert r.json() == {"updated": 0}
    assert c.get("/api/v1/alerts/events", headers=auth()).json()["unread"] == 2
    c.post("/api/v1/alerts/events/read", headers=auth(), json={})
    assert c.get("/api/v1/alerts/events?unread_only=true", headers=auth()).json()["events"] == []

    # Users can't touch each other's rules.
    assert c.delete(f"/api/v1/alerts/rules/{ids[0]}", headers=auth(USER_B)).status_code == 404
    r = c.patch(f"/api/v1/alerts/rules/{ids[0]}", headers=auth(), json={"active": False})
    assert r.json()["active"] is False
    assert c.delete(f"/api/v1/alerts/rules/{ids[0]}", headers=auth()).status_code == 204


def test_crossing_rules_rearm(env):
    import pandas as pd

    from app.db.session import _session_factory
    from app.models import AlertRule
    from app.services import alert_service as alerts
    from app.services import market_data as md

    with _session_factory()() as s:
        inst = md.get_instrument(s, "eq:in:TCS")
    rule = AlertRule(kind="price_above", threshold=100, last_state=None)
    close = pd.Series([90.0, 110.0])
    met, msg, _ = alerts.evaluate_rule(rule, inst, close, [])
    assert met and msg
    rule.last_state = True
    met, msg, _ = alerts.evaluate_rule(rule, inst, pd.Series([110.0, 120.0]), [])
    assert met and msg is None  # still above: no repeat
    rule.last_state = False
    met, msg, _ = alerts.evaluate_rule(rule, inst, pd.Series([90.0, 101.0]), [])
    assert met and msg  # crossed again


def test_volatility_rule(env):
    import pandas as pd

    from app.db.session import _session_factory
    from app.models import AlertRule
    from app.services import alert_service as alerts
    from app.services import market_data as md

    with _session_factory()() as s:
        inst = md.get_instrument(s, "eq:us:AAPL")
    rng = np.random.default_rng(0)
    close = pd.Series(100 * np.cumprod(1 + rng.normal(0, 0.03, 40)))
    rule = AlertRule(kind="volatility_above", threshold=0.3, last_state=None)
    met, msg, details = alerts.evaluate_rule(rule, inst, close, [])
    assert met and details["volatility"] > 0.3 and "a year" in msg
