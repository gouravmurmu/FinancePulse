"""Analytics against hand-calculated expected values (see docs/METHODOLOGY.md)."""

import math
import statistics

import numpy as np
import pandas as pd
import pytest

from app.analytics import metrics as m
from app.analytics import technicals as t
from app.analytics.conventions import mixed_periods_per_year, periods_per_year
from app.analytics.simulation import monte_carlo, stress_test


def series(values, start="2024-01-01", freq="D"):
    return pd.Series(
        values, index=pd.date_range(start, periods=len(values), freq=freq), dtype=float
    )


# --- returns -----------------------------------------------------------------


def test_simple_returns_and_total_return():
    p = series([100, 110, 99, 108.9])
    assert m.simple_returns(p).round(10).tolist() == [0.1, -0.1, 0.1]
    assert m.total_return(p) == pytest.approx(0.089)


def test_normalize_to_100():
    assert m.normalize_to_100(series([50, 75, 25])).tolist() == [100, 150, 50]


def test_cagr_over_two_years():
    p = pd.Series(
        [100.0, 121.0], index=pd.to_datetime(["2020-01-01T00:00:00", "2021-12-31T12:00:00"])
    )
    # 730.5 days = exactly 2 years of 365.25 days; 1.21 ** 0.5 - 1 = 10%.
    assert m.cagr(p) == pytest.approx(0.10, abs=1e-9)


def test_cagr_undefined_for_short_window():
    assert m.cagr(series([100, 101, 102])) is None


# --- annualization -----------------------------------------------------------


def test_annualization_252_vs_365():
    assert periods_per_year("equity") == 252
    assert periods_per_year("index") == 252
    assert periods_per_year("crypto") == 365
    assert mixed_periods_per_year(["crypto", "crypto"]) == 365
    assert mixed_periods_per_year(["crypto", "equity"]) == 252

    r = series([0.01, -0.02] * 15)
    sd = statistics.stdev(r.tolist())
    assert m.annualized_volatility(r, 252) == pytest.approx(sd * math.sqrt(252))
    assert m.annualized_volatility(r, 365) == pytest.approx(sd * math.sqrt(365))


def test_metrics_undefined_with_too_few_observations():
    r = series([0.01] * 10)
    assert m.annualized_volatility(r, 252) is None
    assert m.sharpe_ratio(r, 252) is None
    assert m.historical_var(r) is None


# --- risk-adjusted returns ---------------------------------------------------


def test_sharpe_ratio_hand_calculated():
    r = series([0.02, 0.0] * 10)  # mean 0.01
    sd = math.sqrt(sum((x - 0.01) ** 2 for x in r) / 19)
    expected = 0.01 / sd * math.sqrt(252)
    assert m.sharpe_ratio(r, 252) == pytest.approx(expected)
    assert expected == pytest.approx(15.4725, abs=1e-4)


def test_sharpe_with_risk_free_rate():
    r = series([0.02, 0.0] * 10)
    rf = 0.0252  # 0.0001 per day over 252 days
    sd = math.sqrt(sum((x - 0.01) ** 2 for x in r) / 19)
    assert m.sharpe_ratio(r, 252, rf) == pytest.approx((0.01 - 0.0001) / sd * math.sqrt(252))


def test_sharpe_undefined_for_zero_volatility():
    assert m.sharpe_ratio(series([0.01] * 30), 252) is None


def test_sortino_ratio_hand_calculated():
    r = series([0.02, -0.01] * 10)  # mean 0.005; downside deviation sqrt(0.0001 / 2)
    expected = 0.005 / math.sqrt(0.00005) * math.sqrt(252)
    assert m.sortino_ratio(r, 252) == pytest.approx(expected)
    assert expected == pytest.approx(11.2250, abs=1e-4)


def test_sortino_undefined_without_losses():
    assert m.sortino_ratio(series([0.01, 0.02] * 15), 252) is None


# --- drawdown ----------------------------------------------------------------


def test_max_drawdown_with_recovery():
    p = series([100, 120, 90, 95, 130, 117])
    dd = m.max_drawdown(p)
    assert dd.value == pytest.approx(-0.25)
    assert str(dd.peak_date) == "2024-01-02"
    assert str(dd.trough_date) == "2024-01-03"
    assert str(dd.recovery_date) == "2024-01-05"


def test_max_drawdown_without_recovery():
    dd = m.max_drawdown(series([100, 80, 90]))
    assert dd.value == pytest.approx(-0.2)
    assert dd.recovery_date is None


def test_drawdown_series_never_positive():
    d = m.drawdown_series(series([100, 120, 90, 130]))
    assert d.tolist() == pytest.approx([0, 0, -0.25, 0])


# --- VaR / ES ----------------------------------------------------------------


def test_historical_var_and_es_hand_calculated():
    r = series([round(-0.10 + 0.01 * i, 2) for i in range(20)])  # -0.10 .. 0.09
    # 5% quantile at position 19 * 0.05 = 0.95: -0.10 + 0.95 * 0.01 = -0.0905
    assert m.historical_var(r, 0.95) == pytest.approx(0.0905)
    # Only -0.10 is at or below the threshold.
    assert m.expected_shortfall(r, 0.95) == pytest.approx(0.10)
    # ES is always at least VaR.
    assert m.expected_shortfall(r, 0.99) >= m.historical_var(r, 0.99)


def test_var_rejects_bad_confidence():
    with pytest.raises(ValueError):
        m.historical_var(series([0.0] * 30), 0.05)


# --- beta / correlation ------------------------------------------------------


def test_beta_of_levered_asset():
    bench = series([0.01, -0.02, 0.015, 0.0, -0.005] * 6)
    assert m.beta(bench * 2, bench) == pytest.approx(2.0)


def test_beta_uses_only_shared_dates():
    bench = series([0.01, -0.02, 0.015, 0.0, -0.005] * 6)
    asset = (bench * 1.5).iloc[3:]
    assert m.beta(asset, bench) == pytest.approx(1.5)


def test_correlation_matrix_perfect_and_inverse():
    a = series([0.01, -0.02, 0.03, -0.01, 0.02])
    df = pd.DataFrame({"a": a, "b": a * 3, "c": -a})
    c = m.correlation_matrix(df)
    assert c.loc["a", "b"] == pytest.approx(1.0)
    assert c.loc["a", "c"] == pytest.approx(-1.0)


# --- technicals --------------------------------------------------------------


def test_sma():
    assert t.sma(series([1, 2, 3, 4, 5]), 3).tolist()[2:] == [2, 3, 4]


def test_ema_seeded_with_sma():
    # span 3 -> alpha 0.5; seed = mean(1, 2, 3) = 2
    out = t.ema(series([1, 2, 3, 4, 5]), 3)
    assert out.isna().tolist()[:2] == [True, True]
    assert out.tolist()[2:] == [2, 3, 4]


def test_rsi_wilder_hand_calculated():
    out = t.rsi(series([1, 2, 1, 2]), period=2)
    assert out.iloc[2] == pytest.approx(50.0)
    assert out.iloc[3] == pytest.approx(75.0)


def test_rsi_edge_cases():
    assert t.rsi(series(range(1, 30)), 14).dropna().eq(100).all()
    assert t.rsi(series([5] * 30), 14).dropna().eq(50).all()


def test_macd_zero_for_flat_prices():
    line, sig, hist = t.macd(series([10.0] * 60))
    assert line.dropna().abs().max() == pytest.approx(0)
    assert hist.dropna().abs().max() == pytest.approx(0)


def test_bollinger_bands():
    mid, up, lo = t.bollinger(series([1, 3] * 10), window=4, num_std=2)
    # window [1,3,1,3]: mean 2, population sd 1
    assert mid.iloc[-1] == pytest.approx(2)
    assert up.iloc[-1] == pytest.approx(4)
    assert lo.iloc[-1] == pytest.approx(0)


# --- simulation --------------------------------------------------------------


def test_monte_carlo_is_reproducible_with_seed():
    kw = dict(
        initial_value=1000,
        weights=np.array([0.6, 0.4]),
        mean_returns=np.array([0.0004, 0.0002]),
        cov=np.array([[1e-4, 2e-5], [2e-5, 4e-5]]),
        horizon_days=30,
        paths=500,
    )
    a = monte_carlo(seed=7, **kw)
    b = monte_carlo(seed=7, **kw)
    c = monte_carlo(seed=8, **kw)
    assert a.percentiles == b.percentiles
    assert a.percentiles != c.percentiles
    assert len(a.percentiles[50]) == 31
    assert a.percentiles[5][-1] <= a.percentiles[50][-1] <= a.percentiles[95][-1]


def test_monte_carlo_zero_volatility_is_deterministic():
    res = monte_carlo(
        initial_value=100,
        weights=np.array([1.0]),
        mean_returns=np.array([0.001]),
        cov=np.array([[0.0]]),
        horizon_days=10,
        paths=100,
    )
    assert res.percentiles[50][-1] == pytest.approx(100 * 1.001**10, rel=1e-6)
    assert res.probability_of_loss == 0.0


def test_monte_carlo_validates_inputs():
    with pytest.raises(ValueError):
        monte_carlo(100, np.array([0.5, 0.4]), np.zeros(2), np.eye(2), 10, 100)


def test_stress_test_contributions():
    out = stress_test({"a": 0.6, "b": 0.4}, {"a": -0.2, "b": 0.1})
    assert out["a"] == pytest.approx(-0.12)
    assert out["b"] == pytest.approx(0.04)
    assert out["total"] == pytest.approx(-0.08)
