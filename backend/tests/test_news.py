"""News: Finnhub parsing, crypto matching, idempotent storage, sentiment scoring."""

import os
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest

from app.data.universe import BY_ID, UNIVERSE
from app.providers import finnhub
from app.providers.base import ProviderError

NOW = int(datetime(2026, 10, 9, 14, tzinfo=UTC).timestamp())


def _row(i, headline, url="https://example.com/a", **kw):
    return {"id": i, "datetime": NOW, "headline": headline, "source": "Reuters", "url": url, **kw}


def test_normalize_keeps_only_complete_items_and_trims():
    rows = [
        _row(1, "  Apple   beats  ", summary="x" * 900),
        _row(2, "", url="https://example.com/b"),  # no headline
        _row(3, "No link", url="javascript:alert(1)"),
        {"id": 4, "headline": "No time", "url": "https://example.com/c"},
    ]
    items = finnhub.normalize(rows, {"eq:us:AAPL"})
    assert len(items) == 1
    assert items[0].headline == "Apple beats"
    assert len(items[0].summary) == finnhub.SUMMARY_MAX
    assert items[0].published_at == datetime(2026, 10, 9, 14, tzinfo=UTC)
    assert items[0].instrument_ids == {"eq:us:AAPL"}


def test_crypto_matching_uses_names_and_capital_tickers():
    m = finnhub.crypto_matchers(UNIVERSE)
    items = finnhub.normalize(
        [
            _row(1, "Bitcoin and ETH rally", url="https://e.com/1"),
            _row(2, "Solana outage", url="https://e.com/2"),
            _row(3, "Bake a sol-ar cake at home", url="https://e.com/3"),
            _row(4, "Markets are calm", url="https://e.com/4"),
        ],
        set(),
    )
    tagged = {i.headline: i.instrument_ids for i in finnhub.tag_crypto(items, m)}
    assert tagged == {
        "Bitcoin and ETH rally": {"crypto:BTC", "crypto:ETH"},
        "Solana outage": {"crypto:SOL"},
    }


def test_company_symbol_only_for_us_listings():
    assert finnhub.company_symbol(BY_ID["eq:us:AAPL"]) == "AAPL"
    assert finnhub.company_symbol(BY_ID["etf:us:GLD"]) == "GLD"
    assert finnhub.company_symbol(BY_ID["eq:in:TCS"]) is None
    assert finnhub.company_symbol(BY_ID["crypto:BTC"]) is None


def test_fetch_sends_key_in_header_and_maps_errors(monkeypatch):
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["token"] = req.headers.get("X-Finnhub-Token")
        seen["params"] = dict(req.url.params)
        if req.url.params.get("symbol") == "MSFT":
            return httpx.Response(429)
        return httpx.Response(200, json=[_row(9, "Apple news")])

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    with pytest.raises(ProviderError, match="not set"):
        finnhub.fetch_company_news(
            client, BY_ID["eq:us:AAPL"], date(2026, 10, 1), date(2026, 10, 9)
        )
    monkeypatch.setenv("FINNHUB_API_KEY", "k")
    items = finnhub.fetch_company_news(
        client, BY_ID["eq:us:AAPL"], date(2026, 10, 1), date(2026, 10, 9)
    )
    assert [i.headline for i in items] == ["Apple news"]
    assert seen["token"] == "k" and "token" not in seen["params"]  # noqa: S105 (test key)
    assert seen["params"] == {"symbol": "AAPL", "from": "2026-10-01", "to": "2026-10-09"}
    with pytest.raises(ProviderError, match="429"):
        finnhub.fetch_company_news(
            client, BY_ID["eq:us:MSFT"], date(2026, 10, 1), date(2026, 10, 9)
        )


@pytest.mark.db
@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set")
def test_store_score_and_serve(monkeypatch):
    url = os.environ["TEST_DATABASE_URL"]
    os.environ["DATABASE_URL"] = url
    from alembic import command
    from alembic.config import Config
    from fastapi.testclient import TestClient
    from sqlalchemy import text

    from app.core.config import Settings, get_settings
    from app.db.session import _session_factory, get_engine
    from app.main import create_app
    from app.services import cache, market_store, news_service
    from jobs import score_sentiment

    for f in (get_settings, get_engine, _session_factory):
        f.cache_clear()
    cache.clear()
    command.upgrade(Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini")), "head")
    now = datetime.now(UTC)
    rows = [
        {
            **_row(1, "Apple beats estimates", url="https://e.com/1"),
            "datetime": int(now.timestamp()) - 3600,
        },
        {
            **_row(2, "Apple faces lawsuit", url="https://e.com/2"),
            "datetime": int(now.timestamp()) - 86400,
        },
    ]
    with _session_factory()() as s:
        s.execute(text("delete from news_articles"))
        market_store.sync_universe(s, UNIVERSE)
        items = finnhub.normalize(rows, {"eq:us:AAPL"})
        assert news_service.store_items(s, items, now) == (2, 2)
        # Same headlines again, now also linked to MSFT: no duplicates, one new link each.
        for i in items:
            i.instrument_ids.add("eq:us:MSFT")
        assert news_service.store_items(s, items, now) == (0, 2)
        s.commit()

        def fake(texts):
            return [
                {"positive": 0.9, "neutral": 0.08, "negative": 0.02}
                if "beats" in t
                else {"positive": 0.05, "neutral": 0.15, "negative": 0.8}
                for t in texts
            ]

        assert score_sentiment.score(s, fake, 100, model="test") == 2
        assert score_sentiment.score(s, fake, 100, model="test") == 0  # nothing left

    monkeypatch.setenv("FINNHUB_API_KEY", "k")
    c = TestClient(create_app(Settings()))
    body = c.get("/api/v1/instruments/eq:us:AAPL/news").json()
    assert body["configured"] and body["coverage_note"] is None
    heads = [(a["headline"], a["sentiment"]["label"]) for a in body["articles"]]
    assert heads == [("Apple beats estimates", "positive"), ("Apple faces lawsuit", "negative")]
    tones = {p["date"]: p["tone"] for p in body["trend"]["points"]}
    assert len(tones) in (1, 2)  # both may fall on the same UTC day
    assert all(-1 <= t <= 1 for t in tones.values())
    tcs = c.get("/api/v1/instruments/eq:in:TCS/news").json()
    assert tcs["articles"] == [] and "US-listed" in tcs["coverage_note"]
    assert (now - timedelta(days=1)).date() <= datetime.fromisoformat(
        body["articles"][0]["published_at"]
    ).date()
