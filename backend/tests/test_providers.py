from datetime import UTC, date, datetime

import pandas as pd

from app.data.universe import BY_ID, UNIVERSE
from app.providers import coingecko, yahoo
from app.providers.base import Observation, assess_quality

RETRIEVED = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


def yahoo_frame(rows, tz="America/New_York"):
    idx = pd.DatetimeIndex([r[0] for r in rows], name="Date").tz_localize(tz)
    return pd.DataFrame(
        [r[1:] for r in rows],
        index=idx,
        columns=["Open", "High", "Low", "Close", "Adj Close", "Volume"],
    )


def test_universe_ids_unique_and_well_formed():
    ids = [i.id for i in UNIVERSE]
    assert len(ids) == len(set(ids))
    for inst in UNIVERSE:
        assert inst.currency in {"USD", "INR", "EUR", "GBP", "JPY", "HKD"}
        assert "yfinance" in inst.aliases
        assert inst.region in {"global", "india"}
    # Metals are labelled as futures or ETFs, never as spot.
    for inst in UNIVERSE:
        if inst.attributes.get("metal"):
            assert "spot" not in inst.name.lower()
            assert inst.price_definition


def test_normalize_history_marks_today_as_delayed():
    inst = BY_ID["eq:us:AAPL"]
    frame = yahoo_frame(
        [
            ("2026-10-08", 100, 102, 99, 101, 100.5, 1_000_000),
            ("2026-10-09", 101, 103, 100, 102, 101.5, 1_100_000),
            ("2026-10-10", 102, 104, 101, 103, 103, 500_000),
        ]
    )
    obs = yahoo.normalize_history(frame, inst, RETRIEVED)
    assert [o.trading_date for o in obs] == [
        date(2026, 10, 8),
        date(2026, 10, 9),
        date(2026, 10, 10),
    ]
    assert [o.quote_type for o in obs] == ["eod", "eod", "delayed"]
    assert obs[0].adj_close == 100.5
    assert obs[0].volume == 1_000_000
    assert obs[0].currency == "USD"
    assert obs[0].provenance["symbol"] == "AAPL"


def test_normalize_history_drops_missing_and_nonpositive_closes():
    inst = BY_ID["eq:us:AAPL"]
    frame = yahoo_frame(
        [
            ("2026-10-06", 100, 102, 99, float("nan"), None, 0),
            ("2026-10-07", 100, 102, 99, 0, 0, 0),
            ("2026-10-08", 100, 102, 99, 101, 101, 10),
        ]
    )
    obs = yahoo.normalize_history(frame, inst, RETRIEVED)
    assert [o.close for o in obs] == [101]


def test_index_volume_is_dropped():
    inst = BY_ID["idx:in:NIFTY50"]
    frame = yahoo_frame([("2026-10-08", 1, 2, 1, 2, 2, 12345)], tz="Asia/Kolkata")
    assert yahoo.normalize_history(frame, inst, RETRIEVED)[0].volume is None


def test_crypto_bars_are_eod_in_utc():
    inst = BY_ID["crypto:BTC"]
    frame = yahoo_frame([("2026-10-10", 1, 2, 1, 2, 2, 5)], tz="UTC")
    assert yahoo.normalize_history(frame, inst, RETRIEVED)[0].quote_type == "eod"


def _obs(close, high=None, low=None):
    return Observation(
        instrument_id="x",
        provider="p",
        trading_date=date(2026, 1, 1),
        retrieved_at=RETRIEVED,
        currency="USD",
        close=close,
        high=high,
        low=low,
    )


def test_quality_assessment():
    assert assess_quality(_obs(10, 11, 9), 10, "equity") == "ok"
    assert assess_quality(_obs(-1), None, "equity") == "rejected"
    assert assess_quality(_obs(10, 9, 11), None, "equity") == "suspect"  # high < low
    assert assess_quality(_obs(20, 11, 9), None, "equity") == "suspect"  # close outside range
    assert assess_quality(_obs(16), 10, "equity") == "suspect"  # +60% day
    assert assess_quality(_obs(16), 10, "crypto") == "ok"  # crypto allows larger moves


def test_coingecko_markets_normalization():
    payload = [
        {
            "id": "bitcoin",
            "current_price": 65000.5,
            "market_cap": 1.28e12,
            "total_volume": 3.1e10,
            "circulating_supply": 19750000.0,
            "total_supply": 21000000.0,
            "max_supply": 21000000.0,
            "last_updated": "2026-10-10T11:58:31.123Z",
        },
        {"id": "unknown-coin", "current_price": 1},
    ]
    snaps = coingecko.normalize_markets(payload, UNIVERSE, RETRIEVED)
    assert len(snaps) == 1
    s = snaps[0]
    assert s.instrument_id == "crypto:BTC"
    assert s.market_cap == 1.28e12
    assert s.as_of == datetime(2026, 10, 10, 11, 58, 31, 123000, tzinfo=UTC)
