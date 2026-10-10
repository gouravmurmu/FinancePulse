"""Adapters against real provider payloads recorded by record-fixtures.yml
(Yahoo daily history and CoinGecko markets, 10 Oct 2026)."""

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from app.data.universe import BY_ID, UNIVERSE
from app.providers import coingecko, yahoo

DIR = Path(__file__).parent / "fixtures" / "recorded"
# File -> (instrument, time zone yfinance used for the index when recorded).
CASES = {
    "yahoo_AAPL.csv": ("eq:us:AAPL", "America/New_York"),
    "yahoo_idx_NSEI.csv": ("idx:in:NIFTY50", "Asia/Kolkata"),
    "yahoo_BTC-USD.csv": ("crypto:BTC", "UTC"),
    "yahoo_GC_F.csv": ("metal:XAU:comex-fut", "America/New_York"),
    # Yahoo dates FX bars at London midnight, not UTC.
    "yahoo_USDINR_X.csv": ("fx:USDINR", "Europe/London"),
    "yahoo_RELIANCE_NS.csv": ("eq:in:RELIANCE", "Asia/Kolkata"),
}


def load(name: str) -> tuple[pd.DataFrame, list[str]]:
    raw = pd.read_csv(DIR / name)
    # yfinance indexes bars at local midnight with the exchange's UTC offset.
    local_dates = [s[:10] for s in raw["Date"]]
    raw.index = pd.DatetimeIndex(pd.to_datetime(raw.pop("Date"), utc=True), name="Date")
    return raw, local_dates


@pytest.mark.parametrize(("name", "case"), CASES.items())
def test_yahoo_recorded_history_normalizes(name, case):
    inst_id, tz = case
    frame, local_dates = load(name)
    inst = BY_ID[inst_id]
    frame.index = frame.index.tz_convert(tz)
    last = date.fromisoformat(local_dates[-1])
    retrieved = datetime.combine(last + timedelta(days=2), datetime.min.time(), UTC)
    obs = yahoo.normalize_history(frame, inst, retrieved)
    assert len(obs) == len(frame)
    assert [o.trading_date.isoformat() for o in obs] == local_dates
    assert all(o.quote_type == "eod" for o in obs)
    assert all(o.quality_status == "ok" for o in obs)
    assert all(o.currency == inst.currency for o in obs)
    if inst.asset_class == "index":
        assert all(o.volume is None for o in obs)


def test_coingecko_recorded_markets_normalize():
    payload = json.loads((DIR / "coingecko_markets.json").read_text())
    snaps = coingecko.normalize_markets(payload, UNIVERSE, datetime(2026, 10, 10, tzinfo=UTC))
    by_id = {s.instrument_id: s for s in snaps}
    assert {"crypto:BTC", "crypto:ETH", "crypto:SOL"} <= set(by_id)
    btc = by_id["crypto:BTC"]
    assert btc.market_cap and btc.market_cap > 1e11
    assert btc.max_supply == 21_000_000
    assert btc.as_of.tzinfo is not None
