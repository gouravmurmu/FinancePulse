"""Provider adapter contract.

Adapters are the only code that knows provider symbols, payload shapes and
rate limits. Everything they return is normalized to canonical instrument IDs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass
class Observation:
    instrument_id: str
    provider: str
    trading_date: date
    retrieved_at: datetime
    currency: str
    close: float
    open: float | None = None
    high: float | None = None
    low: float | None = None
    adj_close: float | None = None
    volume: float | None = None
    quote_type: str = "eod"  # eod for completed sessions, delayed for today's bar
    quality_status: str = "ok"
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass
class Snapshot:
    """Latest non-price stats (market cap, supply, volume) for an instrument."""

    instrument_id: str
    provider: str
    as_of: datetime
    retrieved_at: datetime
    market_cap: float | None = None
    circulating_supply: float | None = None
    total_supply: float | None = None
    max_supply: float | None = None
    volume_24h: float | None = None
    price: float | None = None


class ProviderError(Exception):
    """A provider call failed. The job logs it and moves on to the next instrument."""


def finite(value: Any) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def assess_quality(obs: Observation, previous_close: float | None, asset_class: str) -> str:
    """Flag bars that look wrong instead of silently trusting them.

    * rejected: non-positive close (not stored)
    * suspect: high < low, close far outside the day's range, or an implausible
      one-day move (>50% for non-crypto, >80% for crypto)
    """
    if obs.close <= 0:
        return "rejected"
    if obs.high is not None and obs.low is not None:
        if obs.high < obs.low:
            return "suspect"
        tolerance = 0.01 * obs.close
        if obs.close > obs.high + tolerance or obs.close < obs.low - tolerance:
            return "suspect"
    if previous_close and previous_close > 0:
        move = abs(obs.close / previous_close - 1)
        limit = 0.8 if asset_class == "crypto" else 0.5
        if move > limit:
            return "suspect"
    return "ok"
