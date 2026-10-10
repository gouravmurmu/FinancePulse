"""Return and risk metrics on daily price series.

All functions take a pandas Series of prices or returns indexed by date and
return plain floats (or None when undefined). Sign conventions:

* Returns are simple returns, r_t = P_t / P_{t-1} - 1.
* VaR and expected shortfall are reported as positive loss fractions:
  a 95% one-day VaR of 0.03 means "on 5% of days the loss was at least 3%".
* Max drawdown is reported as a negative fraction (-0.25 = 25% below the peak).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from app.analytics.conventions import MIN_OBSERVATIONS

# Treat dispersion below this as zero (floating-point noise on constant series).
_EPS = 1e-12


def simple_returns(prices: pd.Series) -> pd.Series:
    prices = prices.dropna()
    prices = prices[prices > 0]
    return prices.pct_change().dropna()


def normalize_to_100(prices: pd.Series) -> pd.Series:
    prices = prices.dropna()
    if prices.empty:
        return prices
    return prices / prices.iloc[0] * 100.0


def total_return(prices: pd.Series) -> float | None:
    prices = prices.dropna()
    if len(prices) < 2 or prices.iloc[0] <= 0:
        return None
    return float(prices.iloc[-1] / prices.iloc[0] - 1)


def cagr(prices: pd.Series) -> float | None:
    """Compound annual growth rate using actual calendar time elapsed."""
    prices = prices.dropna()
    if len(prices) < 2 or prices.iloc[0] <= 0 or prices.iloc[-1] <= 0:
        return None
    elapsed = pd.Timestamp(prices.index[-1]) - pd.Timestamp(prices.index[0])
    days = elapsed.total_seconds() / 86400
    if days < 30:
        return None
    years = days / 365.25
    return float((prices.iloc[-1] / prices.iloc[0]) ** (1 / years) - 1)


def annualized_volatility(returns: pd.Series, periods: int) -> float | None:
    returns = returns.dropna()
    if len(returns) < MIN_OBSERVATIONS:
        return None
    return float(returns.std(ddof=1) * math.sqrt(periods))


def annualized_mean_return(returns: pd.Series, periods: int) -> float | None:
    returns = returns.dropna()
    if len(returns) < MIN_OBSERVATIONS:
        return None
    return float(returns.mean() * periods)


def sharpe_ratio(returns: pd.Series, periods: int, risk_free_annual: float = 0.0) -> float | None:
    """(mean excess return / std of returns), annualized by sqrt(periods)."""
    returns = returns.dropna()
    if len(returns) < MIN_OBSERVATIONS:
        return None
    excess = returns - risk_free_annual / periods
    sd = excess.std(ddof=1)
    if not np.isfinite(sd) or sd < _EPS:
        return None
    return float(excess.mean() / sd * math.sqrt(periods))


def sortino_ratio(returns: pd.Series, periods: int, risk_free_annual: float = 0.0) -> float | None:
    """Mean excess return over downside deviation (target = risk-free rate)."""
    returns = returns.dropna()
    if len(returns) < MIN_OBSERVATIONS:
        return None
    excess = returns - risk_free_annual / periods
    downside = np.minimum(excess.to_numpy(), 0.0)
    dd = math.sqrt(float(np.mean(downside**2)))
    if dd < _EPS:
        return None
    return float(excess.mean() / dd * math.sqrt(periods))


def drawdown_series(prices: pd.Series) -> pd.Series:
    prices = prices.dropna()
    running_peak = prices.cummax()
    return prices / running_peak - 1.0


@dataclass(frozen=True)
class MaxDrawdown:
    value: float
    peak_date: date
    trough_date: date
    recovery_date: date | None


def max_drawdown(prices: pd.Series) -> MaxDrawdown | None:
    prices = prices.dropna()
    if len(prices) < 2:
        return None
    dd = drawdown_series(prices)
    trough = dd.idxmin()
    value = float(dd.loc[trough])
    peak = prices.loc[:trough].idxmax()
    after = prices.loc[trough:]
    recovered = after[after >= prices.loc[peak]]
    recovery = recovered.index[0] if not recovered.empty and value < 0 else None
    return MaxDrawdown(
        value=value,
        peak_date=pd.Timestamp(peak).date(),
        trough_date=pd.Timestamp(trough).date(),
        recovery_date=pd.Timestamp(recovery).date() if recovery is not None else None,
    )


def historical_var(returns: pd.Series, confidence: float = 0.95) -> float | None:
    """Historical one-period VaR as a positive loss fraction.

    Uses the empirical (1 - confidence) quantile with linear interpolation.
    """
    _check_confidence(confidence)
    returns = returns.dropna()
    if len(returns) < MIN_OBSERVATIONS:
        return None
    q = float(np.quantile(returns.to_numpy(), 1 - confidence))
    return -q


def expected_shortfall(returns: pd.Series, confidence: float = 0.95) -> float | None:
    """Average loss on periods at or beyond the VaR threshold (positive fraction)."""
    _check_confidence(confidence)
    returns = returns.dropna()
    if len(returns) < MIN_OBSERVATIONS:
        return None
    arr = returns.to_numpy()
    q = np.quantile(arr, 1 - confidence)
    tail = arr[arr <= q]
    return float(-tail.mean())


def beta(asset_returns: pd.Series, benchmark_returns: pd.Series) -> float | None:
    """Cov(asset, benchmark) / Var(benchmark) on dates both series share."""
    joined = pd.concat([asset_returns, benchmark_returns], axis=1, join="inner").dropna()
    if len(joined) < MIN_OBSERVATIONS:
        return None
    var_b = joined.iloc[:, 1].var(ddof=1)
    if var_b < _EPS:
        return None
    cov = joined.iloc[:, 0].cov(joined.iloc[:, 1], ddof=1)
    return float(cov / var_b)


def correlation_matrix(returns: pd.DataFrame) -> pd.DataFrame:
    """Pearson correlation on dates where all series have a return."""
    return returns.dropna().corr()


def rolling_volatility(returns: pd.Series, window: int, periods: int) -> pd.Series:
    return (returns.rolling(window).std(ddof=1) * math.sqrt(periods)).dropna()


def rolling_correlation(a: pd.Series, b: pd.Series, window: int) -> pd.Series:
    joined = pd.concat([a, b], axis=1, join="inner").dropna()
    return joined.iloc[:, 0].rolling(window).corr(joined.iloc[:, 1]).dropna()


def _check_confidence(confidence: float) -> None:
    if not 0.5 < confidence < 1:
        raise ValueError("confidence must be between 0.5 and 1")
