"""Portfolio accounting against hand-calculated values."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from app.analytics.portfolio import (
    TROY_OUNCE_GRAMS,
    LedgerError,
    Trade,
    build_positions,
    daily_series,
    risk_contributions,
    to_valuation_units,
    value_position,
)

D = date


def t(side, d, q, p, fees=0.0, fx=1.0, inst="A", seq=0):
    return Trade(inst, side, d, q, p, fees, fx, seq)


def test_weighted_average_cost_and_realized_pnl():
    pos = build_positions(
        [
            t("buy", D(2026, 1, 2), 10, 100, fees=5),
            t("buy", D(2026, 2, 2), 10, 120, fees=5),
            t("sell", D(2026, 3, 2), 5, 130, fees=2),
        ]
    )["A"]
    # cost 1005 + 1205 = 2210 for 20 units -> 110.5 average
    # sell 5: proceeds 650 - 2 = 648, cost out 2210 / 4 = 552.5 -> realized 95.5
    assert pos.quantity == pytest.approx(15)
    assert pos.cost_local == pytest.approx(1657.5)
    assert pos.average_cost == pytest.approx(110.5)
    assert pos.realized_local == pytest.approx(95.5)
    assert pos.fees_local == pytest.approx(12)
    v = value_position(pos, 140, 1.0)
    assert v.value_local == pytest.approx(2100)
    assert v.unrealized_local == pytest.approx(442.5)


def test_full_exit_resets_cost():
    pos = build_positions([t("buy", D(2026, 1, 2), 3, 10), t("sell", D(2026, 1, 3), 3, 12)])["A"]
    assert pos.quantity == 0 and pos.cost_local == 0 and pos.average_cost is None
    assert pos.realized_local == pytest.approx(6)


def test_fx_effect_is_separated_from_price_effect():
    # INR portfolio holding a USD stock: bought at 80 INR/USD, now 85.
    pos = build_positions([t("buy", D(2026, 1, 2), 10, 100, fx=80)])["A"]
    v = value_position(pos, 110, 85)
    assert v.value_base == pytest.approx(93_500)
    assert v.unrealized_base == pytest.approx(13_500)
    assert v.price_effect_base == pytest.approx(8_500)  # 100 USD gain at 85
    assert v.fx_effect_base == pytest.approx(5_000)  # 1000 USD cost * (85 - 80)
    assert v.price_effect_base + v.fx_effect_base == pytest.approx(v.unrealized_base)


def test_realized_pnl_in_base_currency_uses_both_trade_rates():
    pos = build_positions(
        [t("buy", D(2026, 1, 2), 10, 100, fx=80), t("sell", D(2026, 2, 2), 10, 100, fx=84)]
    )["A"]
    assert pos.realized_local == pytest.approx(0)
    assert pos.realized_base == pytest.approx(1000 * 84 - 1000 * 80)


def test_selling_more_than_held_is_rejected():
    with pytest.raises(LedgerError, match="selling 1 on 2 Jan 2026, but only 0 held then"):
        build_positions([t("sell", D(2026, 1, 2), 1, 10), t("buy", D(2026, 1, 5), 1, 10)])


def test_same_day_buy_is_applied_before_sell():
    pos = build_positions([t("sell", D(2026, 1, 2), 1, 11, seq=1), t("buy", D(2026, 1, 2), 1, 10)])
    assert pos["A"].realized_local == pytest.approx(1)


def test_grams_are_valued_per_troy_ounce():
    q, p = to_valuation_units(TROY_OUNCE_GRAMS * 2, 100.0, "gram")
    assert q == pytest.approx(2)
    assert p == pytest.approx(100 * TROY_OUNCE_GRAMS)
    assert to_valuation_units(5, 7, "troy_oz") == (5, 7)


def _cal(n):
    return pd.date_range("2026-01-05", periods=n, freq="B")


def test_time_weighted_return_ignores_deposits():
    cal = _cal(4)
    prices = pd.DataFrame({"A": [100.0, 110.0, 121.0, 110.0]}, index=cal)
    fx = pd.DataFrame({"A": 1.0}, index=cal)
    trades = [
        t("buy", cal[0].date(), 1, 100),
        # Adding money mid-way must not show up as performance.
        t("buy", cal[2].date(), 0.5, 121),
    ]
    s = daily_series(trades, prices, fx, cal)
    assert s.value.tolist() == pytest.approx([100, 110, 181.5, 165])
    # Returns equal the asset's own daily returns.
    assert s.returns.tolist() == pytest.approx([0, 0.1, 0.1, 110 / 121 - 1])
    assert s.index.iloc[-1] == pytest.approx(110)


def test_time_weighted_return_through_a_sale():
    cal = _cal(3)
    prices = pd.DataFrame({"A": [100.0, 120.0, 60.0]}, index=cal)
    fx = pd.DataFrame({"A": 1.0}, index=cal)
    trades = [t("buy", cal[0].date(), 2, 100), t("sell", cal[1].date(), 2, 120)]
    s = daily_series(trades, prices, fx, cal)
    # Sold everything at 120: +20%, then flat (no exposure to the fall to 60).
    assert s.returns.tolist() == pytest.approx([0, 0.2, 0])
    assert s.index.iloc[-1] == pytest.approx(120)


def test_first_day_return_is_close_versus_trade_price():
    cal = _cal(2)
    prices = pd.DataFrame({"A": [105.0, 105.0]}, index=cal)
    fx = pd.DataFrame({"A": 1.0}, index=cal)
    s = daily_series([t("buy", cal[0].date(), 1, 100, fees=0)], prices, fx, cal)
    assert s.returns.iloc[0] == pytest.approx(0.05)


def test_weekend_trade_lands_on_next_trading_day():
    cal = _cal(2)  # Mon 5 Jan, Tue 6 Jan
    prices = pd.DataFrame({"A": [10.0, 11.0]}, index=cal)
    fx = pd.DataFrame({"A": 1.0}, index=cal)
    s = daily_series([t("buy", D(2026, 1, 3), 1, 10)], prices, fx, cal)
    assert s.value.tolist() == pytest.approx([10, 11])


def test_risk_contributions_sum_to_one_and_match_hand_calc():
    rng = np.random.default_rng(1)
    rets = pd.DataFrame(rng.normal(0, [0.01, 0.03], size=(500, 2)), columns=["A", "B"])
    w = pd.Series({"A": 0.5, "B": 0.5})
    rc = risk_contributions(w, rets)
    assert rc.sum() == pytest.approx(1)
    cov = rets.cov().to_numpy()
    wv = np.array([0.5, 0.5])
    assert rc["B"] == pytest.approx(0.5 * (cov @ wv)[1] / (wv @ cov @ wv))
    assert rc["B"] > rc["A"]
