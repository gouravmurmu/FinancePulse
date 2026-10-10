"""Assistant: tools supply the numbers, budgets are enforced, users stay isolated.
The LLM is replaced by a scripted stand-in; no network calls."""

import json
import os
import time
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest

from app.ai.provider import LLMError, LLMReply, OpenAICompatible, ToolCall

SECRET = "assistant-test-secret-at-least-32-bytes"  # noqa: S105 (test-only key)
USER_A = uuid.UUID("00000000-0000-0000-0000-0000000000a3")
USER_B = uuid.UUID("00000000-0000-0000-0000-0000000000b3")


def auth(user=USER_A):
    claims = {
        "sub": str(user),
        "aud": "authenticated",
        "role": "authenticated",
        "exp": int(time.time()) + 600,
    }
    return {"Authorization": f"Bearer {jwt.encode(claims, SECRET, algorithm='HS256')}"}


class Scripted:
    """Plays back tool calls, then answers using what the tools returned."""

    model = "scripted"

    def __init__(self, calls):
        self.calls = list(calls)
        self.seen = []

    def chat(self, messages, tools):
        self.seen.append(messages)
        if self.calls and tools:
            name, args = self.calls.pop(0)
            return LLMReply(None, [ToolCall(f"c{len(self.seen)}", name, args)], tokens=500)
        last_tool = next(m for m in reversed(messages) if m["role"] == "tool")
        data = json.loads(last_tool["content"])
        return LLMReply(f"[Fact] Result: {json.dumps(data)[:200]}", [], tokens=300)


def test_provider_parses_tool_calls_and_maps_errors(monkeypatch):
    payload = {
        "choices": [
            {
                "message": {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "t1",
                            "type": "function",
                            "function": {
                                "name": "get_quote",
                                "arguments": '{"instrument_id": "x"}',
                            },
                        }
                    ],
                }
            }
        ],
        "usage": {"total_tokens": 123},
    }
    sent = {}

    def fake_post(url, json, headers, timeout):
        sent.update(url=url, body=json, headers=headers)
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(httpx, "post", fake_post)
    p = OpenAICompatible("https://llm.test/v1/", "key", "m")
    r = p.chat([{"role": "user", "content": "hi"}], [{"type": "function"}])
    assert r.tool_calls[0].name == "get_quote" and r.tool_calls[0].arguments == {
        "instrument_id": "x"
    }
    assert r.tokens == 123
    assert sent["url"] == "https://llm.test/v1/chat/completions"
    assert sent["headers"]["Authorization"] == "Bearer key"
    monkeypatch.setattr(httpx, "post", lambda *a, **k: httpx.Response(429))
    with pytest.raises(LLMError) as e:
        p.chat([], [])
    assert e.value.quota


@pytest.fixture(scope="module")
def app_env():
    if not os.getenv("TEST_DATABASE_URL"):
        pytest.skip("TEST_DATABASE_URL not set")
    url = os.environ["TEST_DATABASE_URL"]
    os.environ["DATABASE_URL"] = url
    os.environ["SUPABASE_JWT_SECRET"] = SECRET
    os.environ.pop("SUPABASE_URL", None)
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

    for f in (get_settings, get_engine, _session_factory):
        f.cache_clear()
    cache.clear()
    command.upgrade(Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini")), "head")
    now = datetime.now(UTC)
    days = [now.date() - timedelta(days=i) for i in range(30, 0, -1)]
    with _session_factory()() as s:
        s.execute(text("truncate market_observations, ai_usage"))
        s.execute(text("delete from portfolios"))
        s.execute(text("delete from auth.users where id in (:a, :b)"), {"a": USER_A, "b": USER_B})
        s.execute(
            text("insert into auth.users (id, email) values (:a, 'x@x.test'), (:b, 'y@x.test')"),
            {"a": USER_A, "b": USER_B},
        )
        market_store.sync_universe(s, UNIVERSE)
        market_store.upsert_observations(
            s,
            [
                Observation(
                    instrument_id="eq:us:AAPL",
                    provider="yfinance",
                    trading_date=d,
                    retrieved_at=now,
                    currency="USD",
                    close=200.0 + n,
                    adj_close=200.0 + n,
                )
                for n, d in enumerate(days)
            ],
        )
        s.commit()
    cache.clear()
    settings = Settings(llm_api_key=None, ai_requests_per_user_day=3)
    app = create_app(settings)
    yield {"client": TestClient(app), "app": app, "last": 200.0 + len(days) - 1}
    os.environ.pop("SUPABASE_JWT_SECRET", None)
    for f in (get_settings, get_engine, _session_factory):
        f.cache_clear()
    cache.clear()


def ask(c, text, user=USER_A, **ctx):
    return c.post(
        "/api/v1/assistant/chat",
        headers=auth(user),
        json={"messages": [{"role": "user", "content": text}], "context": ctx},
    )


def test_not_configured_and_sign_in_required(app_env):
    c, app = app_env["client"], app_env["app"]
    app.state.llm_provider = None
    assert c.get("/api/v1/assistant/status").json()["configured"] is False
    assert c.post("/api/v1/assistant/chat", json={"messages": []}).status_code in (401, 422)
    r = ask(c, "How is Apple doing?")
    assert r.status_code == 503 and r.json()["error"]["code"] == "ai_not_configured"


def test_numbers_come_from_tools_and_usage_is_recorded(app_env):
    c, app = app_env["client"], app_env["app"]
    bot = Scripted([("get_quote", {"instrument_id": "eq:us:AAPL"})])
    app.state.llm_provider = bot
    r = ask(c, "What did Apple close at?", instrument_id="eq:us:AAPL")
    assert r.status_code == 200, r.text
    body = r.json()
    # The scripted model only repeats what the tool returned.
    assert f'"price": {app_env["last"]}' in body["answer"]
    assert body["tool_calls"] == [
        {"tool": "get_quote", "arguments": {"instrument_id": "eq:us:AAPL"}, "ok": True}
    ]
    assert any("Yahoo" in s for s in body["sources"])
    assert body["usage"]["tokens"] == 800 and body["usage"]["requests_today"] == 1
    # The page context reached the model as a system note.
    assert any("Apple" in m["content"] for m in bot.seen[0] if m["role"] == "system")


def test_tool_errors_are_returned_not_raised(app_env):
    c, app = app_env["client"], app_env["app"]
    app.state.llm_provider = Scripted([("get_quote", {"instrument_id": "nope:X"})])
    r = ask(c, "Price of nothing?")
    assert r.status_code == 200
    assert r.json()["tool_calls"][0]["ok"] is False
    assert "No instrument" in r.json()["answer"]


def test_portfolios_stay_private(app_env):
    c, app = app_env["client"], app_env["app"]
    pid = c.post("/api/v1/portfolios", headers=auth(USER_B), json={"name": "B's"}).json()["id"]
    app.state.llm_provider = Scripted([("get_portfolio", {"portfolio_id": pid})])
    r = ask(c, "Show me that portfolio", user=USER_A)
    assert r.status_code == 200
    assert "not found" in r.json()["answer"].lower()


def test_daily_request_limit(app_env):
    c, app = app_env["client"], app_env["app"]
    app.state.llm_provider = Scripted([])
    # USER_A has used 3 requests across the tests above; the limit is 3.
    r = ask(c, "One more?")
    assert r.status_code == 429 and r.json()["error"]["code"] == "ai_quota"
    assert "resets" in r.json()["error"]["message"]
    usage = c.get("/api/v1/assistant/usage", headers=auth()).json()
    assert usage == {"requests": 3, "tokens": usage["tokens"], "requests_left": 0}
