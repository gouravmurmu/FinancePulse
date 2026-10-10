"""Robust z-score anomaly flags."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from app.analytics.anomalies import MAD_SCALE, detect, robust_z


def test_robust_z_matches_hand_calculation():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 100.0])
    z = robust_z(s, window=4, min_history=4)
    # window before the last point: 1,2,3,4 -> median 2.5, MAD 1.0
    assert z.iloc[-1] == pytest.approx((100 - 2.5) / (MAD_SCALE * 1.0))
    assert z.iloc[:4].isna().all()  # not enough history: no score, no look-ahead


def test_no_look_ahead():
    rng = np.random.default_rng(0)
    s = pd.Series(rng.normal(size=300))
    z_full = robust_z(s)
    z_cut = robust_z(s.iloc[:200])
    pd.testing.assert_series_equal(z_full.iloc[:200], z_cut)


def _prices(n=400, shock_at=None, shock=0.0, seed=1):
    rng = np.random.default_rng(seed)
    r = rng.normal(0, 0.01, n)
    if shock_at is not None:
        r[shock_at] = shock
    idx = pd.bdate_range("2024-01-01", periods=n)
    return pd.Series(100 * np.cumprod(1 + r), index=idx)


def test_detects_a_large_one_day_move_and_nothing_in_calm_data():
    calm = detect(_prices())
    assert [a for a in calm if a.kind == "return"] == []
    p = _prices(shock_at=350, shock=-0.12)
    hits = [a for a in detect(p) if a.kind == "return"]
    assert [h.observed_at for h in hits] == [p.index[350].date()]
    assert hits[0].zscore < -4


def test_volume_spike_and_since_filter():
    p = _prices()
    vol = pd.Series(1e6, index=p.index) * np.random.default_rng(2).uniform(0.8, 1.2, len(p))
    vol.iloc[390] = 2e7
    hits = [a for a in detect(p, vol) if a.kind == "volume"]
    assert [h.observed_at for h in hits] == [p.index[390].date()]
    assert detect(p, vol, since=date(2030, 1, 1)) == []


def test_short_history_returns_nothing():
    assert detect(_prices(n=50, shock_at=40, shock=0.5)) == []


def test_a_volatility_episode_is_flagged_once_and_rescans_do_not_reflag():
    rng = np.random.default_rng(3)
    r = rng.normal(0, 0.01, 450)
    r[330:400] = rng.normal(0, 0.05, 70)  # a long turbulent stretch
    idx = pd.bdate_range("2024-01-01", periods=450)
    p = pd.Series(100 * np.cumprod(1 + r), index=idx)
    vol = [a for a in detect(p) if a.kind == "volatility"]
    assert len(vol) == 1
    assert vol[0].observed_at >= idx[330].date()
    # An incremental scan starting mid-episode adds nothing new.
    later = idx[345].date()
    assert [a for a in detect(p, since=later) if a.kind == "volatility"] == []
