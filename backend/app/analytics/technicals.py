"""Technical indicators on daily closes. Standard textbook definitions."""

from __future__ import annotations

import pandas as pd


def sma(close: pd.Series, window: int) -> pd.Series:
    return close.rolling(window, min_periods=window).mean()


def ema(close: pd.Series, span: int) -> pd.Series:
    """Exponential moving average with alpha = 2 / (span + 1), seeded by the SMA."""
    alpha = 2 / (span + 1)
    seed = close.iloc[:span].mean() if len(close) >= span else float("nan")
    out = pd.Series(index=close.index, dtype=float)
    if len(close) < span:
        return out
    out.iloc[span - 1] = seed
    prev = seed
    for i in range(span, len(close)):
        prev = alpha * close.iloc[i] + (1 - alpha) * prev
        out.iloc[i] = prev
    return out


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI: averages of gains and losses smoothed with alpha = 1 / period."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    out = pd.Series(index=close.index, dtype=float)
    if len(close) <= period:
        return out
    avg_gain = gain.iloc[1 : period + 1].mean()
    avg_loss = loss.iloc[1 : period + 1].mean()

    def value(g: float, lo: float) -> float:
        if lo == 0:
            return 100.0 if g > 0 else 50.0
        return 100 - 100 / (1 + g / lo)

    out.iloc[period] = value(avg_gain, avg_loss)
    for i in range(period + 1, len(close)):
        avg_gain = (avg_gain * (period - 1) + gain.iloc[i]) / period
        avg_loss = (avg_loss * (period - 1) + loss.iloc[i]) / period
        out.iloc[i] = value(avg_gain, avg_loss)
    return out


def macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Returns (macd line, signal line, histogram)."""
    line = ema(close, fast) - ema(close, slow)
    valid = line.dropna()
    sig = pd.Series(index=close.index, dtype=float)
    if len(valid) >= signal:
        sig.loc[valid.index] = ema(valid, signal)
    return line, sig, line - sig


def bollinger(
    close: pd.Series, window: int = 20, num_std: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Returns (middle, upper, lower) using the population standard deviation."""
    mid = sma(close, window)
    sd = close.rolling(window, min_periods=window).std(ddof=0)
    return mid, mid + num_std * sd, mid - num_std * sd
