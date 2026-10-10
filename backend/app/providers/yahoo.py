"""Yahoo Finance via yfinance: daily bars for equities, indices, ETFs, futures, FX
and crypto.

yfinance is unofficial and intended for personal/educational use. Data is
treated as delayed or end of day and labelled as such everywhere.
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd

from app.data.universe import InstrumentDef
from app.providers.base import Observation, ProviderError, assess_quality, finite

logger = logging.getLogger(__name__)
PROVIDER = "yfinance"


def normalize_history(
    frame: pd.DataFrame, inst: InstrumentDef, retrieved_at: datetime
) -> list[Observation]:
    """Turn a yfinance history frame into observations.

    The frame has a DatetimeIndex (exchange-local, possibly tz-aware) and the
    columns Open, High, Low, Close, Adj Close (optional), Volume. The bar for
    today's (exchange-local) date may still be in progress and is marked
    "delayed"; earlier bars are "eod".
    """
    if frame is None or frame.empty:
        return []
    frame = frame.rename(columns=lambda c: str(c).strip().lower().replace(" ", "_"))
    today_local = retrieved_at.astimezone(ZoneInfo(inst.timezone)).date()
    out: list[Observation] = []
    prev_close: float | None = None
    for ts, row in frame.sort_index().iterrows():
        close = finite(row.get("close"))
        if close is None:
            continue
        d: date = pd.Timestamp(ts).date()
        volume = finite(row.get("volume"))
        obs = Observation(
            instrument_id=inst.id,
            provider=PROVIDER,
            trading_date=d,
            retrieved_at=retrieved_at,
            currency=inst.currency,
            open=finite(row.get("open")),
            high=finite(row.get("high")),
            low=finite(row.get("low")),
            close=close,
            adj_close=finite(row.get("adj_close")),
            # Index and FX "volume" from Yahoo is often 0 or meaningless.
            volume=volume if volume and inst.asset_class not in ("index", "fx") else None,
            quote_type="delayed" if d >= today_local and inst.asset_class != "crypto" else "eod",
            provenance={
                "symbol": inst.aliases[PROVIDER],
                "adjusted": "adj_close: splits+dividends",
            },
        )
        obs.quality_status = assess_quality(obs, prev_close, inst.asset_class)
        if obs.quality_status == "rejected":
            continue
        out.append(obs)
        prev_close = close
    return out


def fetch_history(
    inst: InstrumentDef, start: date, retrieved_at: datetime, retries: int = 3
) -> list[Observation]:
    import yfinance as yf  # jobs-only dependency

    symbol = inst.aliases[PROVIDER]
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            frame = yf.Ticker(symbol).history(
                start=start.isoformat(), interval="1d", auto_adjust=False, actions=False
            )
            return normalize_history(frame, inst, retrieved_at)
        except Exception as exc:  # yfinance raises many types
            last_error = exc
            wait = 2 ** (attempt + 1)
            logger.warning(
                "yahoo_retry", extra={"symbol": symbol, "attempt": attempt + 1, "wait_s": wait}
            )
            time.sleep(wait)
    raise ProviderError(f"{symbol}: {last_error}")
