"""Portfolio accounting: weighted-average cost, P&L and time-weighted returns.

Conventions (docs/METHODOLOGY.md):
- Cost basis is weighted average cost. Buy fees are added to cost; sell fees
  reduce proceeds.
- Amounts are tracked in the instrument's trading currency ("local") and in the
  portfolio's base currency at the FX rate of each trade date ("base").
- Unrealized base-currency P&L splits exactly into a price effect (local P&L at
  today's rate) and an FX effect (cost restated at today's rate minus the
  historical base cost).
- Same-day trades are applied buys first, then in entry order.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

TROY_OUNCE_GRAMS = 31.1034768
_EPS = 1e-9


class LedgerError(ValueError):
    def __init__(self, message: str, trade_date: date, instrument_id: str):
        super().__init__(message)
        self.trade_date = trade_date
        self.instrument_id = instrument_id


@dataclass(frozen=True)
class Trade:
    instrument_id: str
    side: str  # "buy" | "sell"
    trade_date: date
    quantity: float  # in valuation units (shares, or troy ounces for metal)
    price: float  # per valuation unit, local currency
    fees: float  # local currency
    fx: float  # base currency per one unit of local currency on trade_date
    seq: int = 0  # entry order, for same-day ordering


@dataclass
class Position:
    instrument_id: str
    quantity: float = 0.0
    cost_local: float = 0.0
    cost_base: float = 0.0
    realized_local: float = 0.0
    realized_base: float = 0.0
    fees_local: float = 0.0
    first_trade: date | None = None
    trades: int = 0

    @property
    def average_cost(self) -> float | None:
        return self.cost_local / self.quantity if self.quantity > _EPS else None


def to_valuation_units(quantity: float, price: float, unit: str) -> tuple[float, float]:
    """Physical metal entered in grams is valued per troy ounce."""
    if unit == "gram":
        return quantity / TROY_OUNCE_GRAMS, price * TROY_OUNCE_GRAMS
    return quantity, price


def ordered(trades: list[Trade]) -> list[Trade]:
    return sorted(trades, key=lambda t: (t.trade_date, t.side == "sell", t.seq))


def build_positions(trades: list[Trade]) -> dict[str, Position]:
    """Replay the ledger. Raises LedgerError if any sale exceeds the holding."""
    positions: dict[str, Position] = {}
    for t in ordered(trades):
        p = positions.setdefault(t.instrument_id, Position(t.instrument_id))
        p.trades += 1
        p.fees_local += t.fees
        if p.first_trade is None:
            p.first_trade = t.trade_date
        gross = t.quantity * t.price
        if t.side == "buy":
            p.quantity += t.quantity
            p.cost_local += gross + t.fees
            p.cost_base += (gross + t.fees) * t.fx
            continue
        if t.quantity > p.quantity * (1 + 1e-9) + _EPS:
            raise LedgerError(
                f"selling {t.quantity:g} on {t.trade_date.day} {t.trade_date:%b %Y}, "
                f"but only {p.quantity:g} held then",
                t.trade_date,
                t.instrument_id,
            )
        frac = min(1.0, t.quantity / p.quantity)
        out_local, out_base = p.cost_local * frac, p.cost_base * frac
        proceeds = gross - t.fees
        p.realized_local += proceeds - out_local
        p.realized_base += proceeds * t.fx - out_base
        p.cost_local -= out_local
        p.cost_base -= out_base
        p.quantity -= t.quantity
        if p.quantity <= _EPS:
            p.quantity, p.cost_local, p.cost_base = 0.0, 0.0, 0.0
    return positions


@dataclass
class Valuation:
    value_local: float
    value_base: float
    unrealized_local: float
    unrealized_base: float
    price_effect_base: float
    fx_effect_base: float


def value_position(p: Position, price: float, fx_now: float) -> Valuation:
    value_local = p.quantity * price
    value_base = value_local * fx_now
    unrealized_local = value_local - p.cost_local
    return Valuation(
        value_local=value_local,
        value_base=value_base,
        unrealized_local=unrealized_local,
        unrealized_base=value_base - p.cost_base,
        price_effect_base=unrealized_local * fx_now,
        fx_effect_base=p.cost_local * fx_now - p.cost_base,
    )


@dataclass
class DailySeries:
    value: pd.Series  # base-currency market value at each date's close
    flows: pd.Series  # net external cash in (+ buys incl. fees, - sale proceeds)
    returns: pd.Series  # daily time-weighted returns
    index: pd.Series  # growth of 100
    quantities: pd.DataFrame = field(default_factory=pd.DataFrame)


def daily_series(
    trades: list[Trade],
    prices: pd.DataFrame,  # local-currency closes, columns = instrument ids
    fx: pd.DataFrame,  # base per local, columns = instrument ids, same index
    calendar: pd.DatetimeIndex,
) -> DailySeries:
    """Mark the ledger to market on each calendar date (prices carried forward)
    and chain daily time-weighted returns, so deposits and withdrawals don't
    count as performance:
        r_t = (V_t + O_t - I_t) / V_{t-1} - 1
    where I_t is money put in (cost incl. fees) and O_t money taken out (sale
    proceeds net of fees), both in the base currency, i.e. flows happen at the
    close. When a purchase is larger than the existing portfolio (including the
    first purchase) it counts from the start of the day instead,
        r_t = (V_t + O_t) / (V_{t-1} + I_t) - 1,
    so a small base can't produce extreme daily returns."""
    ids = sorted({t.instrument_id for t in trades})
    qty = pd.DataFrame(0.0, index=calendar, columns=ids)
    inflow = pd.Series(0.0, index=calendar)
    outflow = pd.Series(0.0, index=calendar)
    for t in ordered(trades):
        # Trades on non-calendar days (weekends) land on the next calendar date.
        pos = calendar.searchsorted(pd.Timestamp(t.trade_date))
        if pos >= len(calendar):
            continue
        d = calendar[pos]
        gross = t.quantity * t.price
        if t.side == "buy":
            qty.loc[d:, t.instrument_id] += t.quantity
            inflow.loc[d] += (gross + t.fees) * t.fx
        else:
            qty.loc[d:, t.instrument_id] -= t.quantity
            outflow.loc[d] += (gross - t.fees) * t.fx
    qty = qty.clip(lower=0.0)
    px = prices.reindex(calendar).ffill()[ids]
    fxr = fx.reindex(calendar).ffill()[ids]
    value = (qty * px * fxr).sum(axis=1, min_count=1).fillna(0.0)

    prev = value.shift(1).fillna(0.0)
    start_of_day = inflow > prev
    numer = np.where(start_of_day, value + outflow, value + outflow - inflow)
    denom = np.where(start_of_day, prev + inflow, prev)
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.where(denom > _EPS, numer / denom - 1.0, 0.0)
    returns = pd.Series(r, index=calendar).replace([np.inf, -np.inf], 0.0).fillna(0.0)
    active = inflow.gt(0)
    first = active.idxmax() if active.any() else calendar[0]
    returns = returns.loc[first:]
    flows = (inflow - outflow).loc[first:]
    index = 100.0 * (1.0 + returns).cumprod()
    return DailySeries(
        value=value.loc[first:],
        flows=flows,
        returns=returns,
        index=index,
        quantities=qty.loc[first:],
    )


def risk_contributions(weights: pd.Series, returns: pd.DataFrame) -> pd.Series:
    """Share of portfolio variance from each holding: w_i (Σw)_i / wᵀΣw.
    Sums to 1. Undefined (empty) if the portfolio has no variance."""
    cols = [c for c in weights.index if c in returns.columns]
    if not cols:
        return pd.Series(dtype=float)
    w = weights[cols] / weights[cols].sum()
    cov = returns[cols].cov().to_numpy()
    wv = w.to_numpy()
    total = float(wv @ cov @ wv)
    if not np.isfinite(total) or total <= 0:
        return pd.Series(dtype=float)
    return pd.Series(wv * (cov @ wv) / total, index=cols)
