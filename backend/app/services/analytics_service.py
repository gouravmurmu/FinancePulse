"""Analytics composed from stored prices. Pure functions of the database state;
every number the UI shows comes from here, never from the client or an LLM."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.analytics import metrics as m
from app.analytics import technicals as t
from app.analytics.conventions import MIN_OBSERVATIONS, mixed_periods_per_year, periods_per_year
from app.analytics.simulation import monte_carlo, stress_test
from app.core.errors import AppError
from app.data.exchanges import EXCHANGE_TO_SESSION, SESSIONS, is_open
from app.data.universe import DEFAULT_BENCHMARK
from app.services import market_data as md
from app.services.cache import ttl_cache


def today_utc() -> date:
    return datetime.now(UTC).date()


def _f(x: Any) -> float | None:
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _series_points(s: pd.Series, digits: int = 6) -> list[dict[str, Any]]:
    return [
        {"date": d.date().isoformat(), "value": round(float(v), digits)}
        for d, v in s.dropna().items()
    ]


# --- quotes ------------------------------------------------------------------


def display_series(
    session: Session,
    inst: md.InstrumentInfo,
    series: pd.Series,
    currency: str | None,
    start: date | None,
) -> tuple[pd.Series, str, bool]:
    """Convert USD/INR-priced instruments to the requested display currency.
    Index levels, FX rates and other currencies are left as they are."""
    if currency is None or inst.asset_class in ("index", "fx"):
        return series, inst.currency, False
    if inst.currency not in ("USD", "INR"):
        return series, inst.currency, False
    out, converted = md.convert(series, inst.currency, currency, md.fx_series(session, start))
    return out, (currency if converted else inst.currency), converted


def quote(
    session: Session, inst: md.InstrumentInfo, period: str, currency: str | None
) -> dict[str, Any]:
    today = today_utc()
    start = md.period_start(period, today)
    bars = md.load_bars(session, inst.id, start)
    last_date = bars.index[-1].date() if not bars.empty else None
    fresh = md.freshness(
        inst.asset_class, last_date, bars["quote_type"].iloc[-1] if not bars.empty else None, today
    )
    base: dict[str, Any] = {
        "instrument_id": inst.id,
        "name": inst.name,
        "asset_class": inst.asset_class,
        "region": inst.region,
        "freshness": fresh,
        "price": None,
        "change": None,
        "change_pct": None,
        "currency": inst.currency,
        "converted": False,
        "as_of": last_date.isoformat() if last_date else None,
        "sparkline": [],
    }
    if bars.empty:
        return base
    close, ccy, converted = display_series(session, inst, bars["close"], currency, start)
    if len(close) == 0:
        return base
    if period == "1D":
        ref = None if len(close) < 2 else float(close.iloc[-2])
        spark = close.iloc[-2:]
    else:
        ref = float(close.iloc[0]) if len(close) > 1 else None
        spark = close
    last = float(close.iloc[-1])
    # Downsample sparklines to at most ~60 points to keep payloads small.
    step = max(1, len(spark) // 60)
    base.update(
        price=round(last, 6),
        change=round(last - ref, 6) if ref else None,
        change_pct=round(last / ref - 1, 6) if ref else None,
        currency=ccy,
        converted=converted,
        sparkline=[round(float(v), 4) for v in spark.iloc[::step].tolist() + [last]][-61:],
    )
    return base


def market_status(now: datetime) -> list[dict[str, Any]]:
    out = [
        {"session": key, "name": s.name, "timezone": s.timezone, "open": is_open(s, now)}
        for key, s in SESSIONS.items()
    ]
    out.append({"session": "CRYPTO", "name": "Crypto", "timezone": "UTC", "open": True})
    return out


def instrument_session_open(inst: md.InstrumentInfo, now: datetime) -> bool | None:
    if inst.asset_class == "crypto":
        return True
    key = EXCHANGE_TO_SESSION.get(inst.exchange or "")
    return is_open(SESSIONS[key], now) if key else None


# --- overview ----------------------------------------------------------------

OVERVIEW_GROUPS = {
    "global": {
        "indices": [
            "idx:us:SPX",
            "idx:us:IXIC",
            "idx:us:DJI",
            "idx:gb:FTSE",
            "idx:de:DAX",
            "idx:jp:N225",
            "idx:hk:HSI",
            "idx:in:NIFTY50",
        ],
        "comparison": [
            "idx:us:SPX",
            "idx:in:NIFTY50",
            "crypto:BTC",
            "metal:XAU:comex-fut",
            "metal:XAG:comex-fut",
        ],
    },
    "india": {
        "indices": [
            "idx:in:NIFTY50",
            "idx:in:SENSEX",
            "idx:in:BANKNIFTY",
            "idx:in:NIFTYIT",
            "idx:us:SPX",
        ],
        "comparison": [
            "idx:in:NIFTY50",
            "idx:in:BANKNIFTY",
            "etf:in:GOLDBEES",
            "crypto:BTC",
            "idx:us:SPX",
        ],
    },
}
SNAPSHOT_IDS = [
    "crypto:BTC",
    "crypto:ETH",
    "metal:XAU:comex-fut",
    "metal:XAG:comex-fut",
    "fx:USDINR",
]


@ttl_cache(md.CACHE_S)
def overview(session: Session, region: str, currency: str, period: str) -> dict[str, Any]:
    if region not in OVERVIEW_GROUPS:
        raise AppError("invalid_region", "region must be 'global' or 'india'", 422)
    instruments = {i.id: i for i in md.list_instruments(session)}
    groups = OVERVIEW_GROUPS[region]

    def q(ids: list[str]) -> list[dict[str, Any]]:
        return [quote(session, instruments[i], period, currency) for i in ids if i in instruments]

    stock_ids = [
        i.id
        for i in instruments.values()
        if i.asset_class in ("equity", "crypto") and (region == "global" or i.region == "india")
    ]
    stock_quotes = [
        x for x in q(stock_ids) if x["change_pct"] is not None and x["freshness"]["kind"] != "stale"
    ]
    stock_quotes.sort(key=lambda x: x["change_pct"], reverse=True)

    equities = [x for x in q([i for i in stock_ids if instruments[i].asset_class == "equity"])]
    return {
        "region": region,
        "currency": currency,
        "period": period,
        "indices": q(groups["indices"]),
        "snapshots": q(SNAPSHOT_IDS),
        "gainers": [x for x in stock_quotes if x["change_pct"] > 0][:5],
        "losers": [x for x in reversed(stock_quotes) if x["change_pct"] < 0][:5],
        "heatmap": [
            {**x, "sector": instruments[x["instrument_id"]].attributes.get("sector")}
            for x in equities
        ],
        "comparison": compare(
            session, groups["comparison"], period if period != "1D" else "1M", currency
        ),
        "markets": market_status(datetime.now(UTC)),
        "data_status": md.last_job_run(session, "refresh_market_data"),
    }


# --- comparison --------------------------------------------------------------


def compare(session: Session, ids: list[str], period: str, currency: str | None) -> dict[str, Any]:
    """Growth of 100 from the first common date in the period."""
    start = md.period_start(period, today_utc())
    series: dict[str, pd.Series] = {}
    notes: list[str] = []
    for i in ids:
        inst = md.get_instrument(session, i)
        s = md.total_return_series(md.load_bars(session, i, start))
        s, ccy, converted = display_series(session, inst, s, currency, start)
        if converted:
            notes.append(f"{inst.name} converted to {ccy} at daily USD/INR")
        if not s.empty:
            series[i] = s
    if not series:
        return {"period": period, "start": None, "series": [], "notes": notes}
    frame = pd.DataFrame(series).sort_index().ffill()
    frame = frame.dropna()  # start where every series has a value
    if frame.empty:
        return {"period": period, "start": None, "series": [], "notes": notes}
    norm = frame / frame.iloc[0] * 100
    step = max(1, len(norm) // 400)
    norm = norm.iloc[::step]
    return {
        "period": period,
        "start": frame.index[0].date().isoformat(),
        "series": [
            {"instrument_id": c, "points": _series_points(norm[c], 3)} for c in norm.columns
        ],
        "notes": notes,
    }


# --- single-instrument analytics ---------------------------------------------


def history(
    session: Session, inst: md.InstrumentInfo, period: str, currency: str | None
) -> dict[str, Any]:
    start = md.period_start(period, today_utc())
    bars = md.load_bars(session, inst.id, start)
    if bars.empty:
        return {"instrument_id": inst.id, "currency": inst.currency, "converted": False, "bars": []}
    factor = pd.Series(1.0, index=bars.index)
    ccy, converted = inst.currency, False
    if currency and inst.asset_class not in ("index", "fx") and inst.currency in ("USD", "INR"):
        conv, converted = md.convert(
            bars["close"], inst.currency, currency, md.fx_series(session, start)
        )
        if converted:
            factor = (conv / bars["close"]).reindex(bars.index)
            ccy = currency
    out = []
    for d, row in bars.iterrows():
        f = factor.loc[d]
        if not np.isfinite(f):
            continue
        out.append(
            {
                "date": d.date().isoformat(),
                "open": _round(row["open"], f),
                "high": _round(row["high"], f),
                "low": _round(row["low"], f),
                "close": _round(row["close"], f),
                "volume": _f(row["volume"]),
                "quote_type": row["quote_type"],
                "quality": row["quality_status"],
            }
        )
    return {
        "instrument_id": inst.id,
        "currency": ccy,
        "converted": converted,
        "provider": bars["provider"].iloc[-1],
        "retrieved_at": bars["retrieved_at"].iloc[-1],
        "bars": out,
    }


def _round(v: Any, factor: float) -> float | None:
    x = _f(v)
    return round(x * factor, 6) if x is not None else None


def indicators(session: Session, inst: md.InstrumentInfo, period: str) -> dict[str, Any]:
    """Indicators computed on 300 extra days of warm-up, then trimmed to the period."""
    today = today_utc()
    start = md.period_start(period, today)
    warm = (start - timedelta(days=300)) if start else None
    close = md.load_bars(session, inst.id, warm)["close"].dropna()
    if close.empty:
        return {"instrument_id": inst.id, "series": {}}
    macd_line, macd_sig, macd_hist = t.macd(close)
    bb_mid, bb_up, bb_lo = t.bollinger(close)
    raw = {
        "sma_20": t.sma(close, 20),
        "sma_50": t.sma(close, 50),
        "sma_200": t.sma(close, 200),
        "ema_20": t.ema(close, 20),
        "rsi_14": t.rsi(close, 14),
        "macd": macd_line,
        "macd_signal": macd_sig,
        "macd_hist": macd_hist,
        "bb_upper": bb_up,
        "bb_middle": bb_mid,
        "bb_lower": bb_lo,
    }
    cutoff = pd.Timestamp(start) if start else close.index[0]
    return {
        "instrument_id": inst.id,
        "currency": inst.currency,
        "series": {k: _series_points(v[v.index >= cutoff], 4) for k, v in raw.items()},
    }


def instrument_risk(
    session: Session,
    inst: md.InstrumentInfo,
    period: str,
    benchmark_id: str | None,
    confidence: float,
) -> dict[str, Any]:
    start = md.period_start(period, today_utc())
    prices = md.total_return_series(md.load_bars(session, inst.id, start)).dropna()
    ppy = periods_per_year(inst.asset_class)
    rets = m.simple_returns(prices)
    bench_id = benchmark_id or inst.attributes.get("benchmark") or DEFAULT_BENCHMARK[inst.region]
    beta = None
    if bench_id and bench_id != inst.id:
        bench = md.total_return_series(md.load_bars(session, bench_id, start)).dropna()
        beta = m.beta(rets, m.simple_returns(bench))
    dd = m.max_drawdown(prices)
    vol = m.annualized_volatility(rets, ppy)
    result = {
        "instrument_id": inst.id,
        "period": period,
        "observations": int(len(rets)),
        "periods_per_year": ppy,
        "confidence": confidence,
        "benchmark_id": bench_id,
        "metrics": {
            "total_return": m.total_return(prices),
            "cagr": m.cagr(prices),
            "volatility": vol,
            "sharpe": m.sharpe_ratio(rets, ppy),
            "sortino": m.sortino_ratio(rets, ppy),
            "max_drawdown": dd.value if dd else None,
            "max_drawdown_peak": dd.peak_date.isoformat() if dd else None,
            "max_drawdown_trough": dd.trough_date.isoformat() if dd else None,
            "max_drawdown_recovery": dd.recovery_date.isoformat()
            if dd and dd.recovery_date
            else None,
            "var": m.historical_var(rets, confidence),
            "expected_shortfall": m.expected_shortfall(rets, confidence),
            "beta": beta,
        },
        "risk_level": risk_level(vol),
        "drawdown": _series_points(m.drawdown_series(prices), 4) if not prices.empty else [],
        "rolling_volatility": _series_points(m.rolling_volatility(rets, 30, ppy), 4)
        if len(rets) > 30
        else [],
        "assumptions": [
            "Returns use adjusted closes (splits and dividends) where the provider supplies them.",
            f"Annualized with {ppy} periods per year.",
            "Sharpe and Sortino use a 0% risk-free rate.",
            f"VaR and expected shortfall are historical, one-day, at {confidence:.0%} confidence, "
            "reported as positive losses.",
        ],
    }
    if len(rets) < MIN_OBSERVATIONS:
        result["warning"] = (
            f"Only {len(rets)} daily returns in this period; at least {MIN_OBSERVATIONS} are "
            "needed for volatility, ratios and VaR."
        )
    result["insight"] = single_insight(inst.name, result["metrics"], period)
    return result


RISK_THRESHOLDS = {"low": 0.15, "moderate": 0.30}


def risk_level(vol: float | None) -> str | None:
    """Low < 15% annualized volatility <= Moderate < 30% <= High."""
    if vol is None:
        return None
    if vol < RISK_THRESHOLDS["low"]:
        return "low"
    if vol < RISK_THRESHOLDS["moderate"]:
        return "moderate"
    return "high"


PERIOD_WORDS = {
    "1D": "today",
    "1W": "over the past week",
    "1M": "over the past month",
    "3M": "over the past 3 months",
    "6M": "over the past 6 months",
    "YTD": "so far this year",
    "1Y": "over the past year",
    "3Y": "over the past 3 years",
    "5Y": "over the past 5 years",
    "MAX": "over the full history available",
}


def single_insight(name: str, metrics: dict[str, Any], period: str) -> str | None:
    tr, mdd, vol = (
        metrics.get("total_return"),
        metrics.get("max_drawdown"),
        metrics.get("volatility"),
    )
    if tr is None:
        return None
    direction = "gained" if tr >= 0 else "lost"
    text = f"{name} {direction} {abs(tr):.1%} {PERIOD_WORDS.get(period, '')}"
    if mdd is not None and mdd < -0.05:
        text += f", with a worst peak-to-trough fall of {abs(mdd):.1%}"
    if vol is not None:
        text += f" and annualized volatility of {vol:.1%}"
    return text + "."


# --- multi-asset risk lab ----------------------------------------------------


def aligned_returns(
    session: Session, ids: list[str], start: date | None
) -> tuple[pd.DataFrame, int, list[md.InstrumentInfo]]:
    """Returns on common dates. Mixing crypto with exchange-traded assets samples
    crypto on exchange trading days so every return covers the same interval."""
    insts = [md.get_instrument(session, i) for i in ids]
    prices = md.closes_frame(session, ids, start).dropna()
    rets = prices.pct_change().dropna()
    ppy = mixed_periods_per_year([i.asset_class for i in insts])
    return rets, ppy, insts


def risk_lab(
    session: Session, ids: list[str], period: str, confidence: float, window: int
) -> dict[str, Any]:
    if not 2 <= len(ids) <= 8:
        raise AppError("invalid_selection", "Choose between 2 and 8 instruments", 422)
    if not 10 <= window <= 252:
        raise AppError("invalid_window", "Rolling window must be 10 to 252 days", 422)
    start = md.period_start(period, today_utc())
    rets, ppy, insts = aligned_returns(session, ids, start)
    names = {i.id: i.name for i in insts}
    if len(rets) < MIN_OBSERVATIONS:
        raise AppError(
            "insufficient_data",
            f"Only {len(rets)} common trading days in this period; "
            f"need at least {MIN_OBSERVATIONS}.",
            422,
        )
    growth = (1 + rets).cumprod()
    rows = []
    for i in ids:
        r = rets[i]
        g = growth[i]
        dd = m.max_drawdown(
            pd.concat([pd.Series([1.0], index=[g.index[0] - pd.Timedelta(days=1)]), g])
        )
        vol = m.annualized_volatility(r, ppy)
        rows.append(
            {
                "instrument_id": i,
                "name": names[i],
                "total_return": float(g.iloc[-1] - 1),
                "volatility": vol,
                "sharpe": m.sharpe_ratio(r, ppy),
                "sortino": m.sortino_ratio(r, ppy),
                "max_drawdown": dd.value if dd else None,
                "var": m.historical_var(r, confidence),
                "expected_shortfall": m.expected_shortfall(r, confidence),
                "risk_level": risk_level(vol),
            }
        )
    corr = m.correlation_matrix(rets)
    rolling = []
    if len(ids) >= 2 and len(rets) > window:
        rc = m.rolling_correlation(rets[ids[0]], rets[ids[1]], window)
        rolling = _series_points(rc, 4)
    drawdowns = {i: _series_points(m.drawdown_series(growth[i]), 4) for i in ids}
    return {
        "period": period,
        "start": rets.index[0].date().isoformat(),
        "end": rets.index[-1].date().isoformat(),
        "observations": int(len(rets)),
        "periods_per_year": ppy,
        "confidence": confidence,
        "window": window,
        "metrics": rows,
        "correlation": {
            "ids": ids,
            "matrix": [[round(float(corr.loc[a, b]), 4) for b in ids] for a in ids],
        },
        "rolling_correlation": {"pair": ids[:2], "points": rolling},
        "drawdowns": drawdowns,
        "insight": compare_insight(rows),
        "assumptions": [
            "Statistics use only dates on which every selected instrument has a price.",
            f"Annualized with {ppy} periods per year"
            + (
                " (crypto sampled on exchange trading days)."
                if ppy == 252 and any(i.asset_class == "crypto" for i in insts)
                else "."
            ),
            f"VaR and expected shortfall: historical, one-day, {confidence:.0%} confidence, "
            "positive numbers are losses.",
            "Sharpe and Sortino use a 0% risk-free rate.",
        ],
    }


def compare_insight(rows: list[dict[str, Any]]) -> str | None:
    vols = [(r["name"], r["volatility"]) for r in rows if r["volatility"]]
    if len(vols) < 2:
        return None
    hi = max(vols, key=lambda x: x[1])
    lo = min(vols, key=lambda x: x[1])
    if lo[1] <= 0:
        return None
    return f"{hi[0]} was {hi[1] / lo[1]:.1f}× as volatile as {lo[0]} over this period."


def run_monte_carlo(
    session: Session,
    weights: dict[str, float],
    initial_value: float,
    horizon_days: int,
    paths: int,
    seed: int,
    lookback: str,
) -> dict[str, Any]:
    ids = list(weights)
    if not 1 <= len(ids) <= 8:
        raise AppError("invalid_selection", "Choose between 1 and 8 instruments", 422)
    total = sum(weights.values())
    if total <= 0 or any(w < 0 for w in weights.values()):
        raise AppError(
            "invalid_weights", "Weights must be non-negative and sum to more than 0", 422
        )
    w = np.array([weights[i] / total for i in ids])
    start = md.period_start(lookback, today_utc())
    if len(ids) == 1:
        inst = md.get_instrument(session, ids[0])
        prices = md.total_return_series(md.load_bars(session, ids[0], start)).dropna()
        rets = m.simple_returns(prices).to_frame(ids[0])
        ppy = periods_per_year(inst.asset_class)
    else:
        rets, ppy, _ = aligned_returns(session, ids, start)
    if len(rets) < 60:
        raise AppError(
            "insufficient_data", "Need at least 60 days of history to estimate inputs", 422
        )
    try:
        res = monte_carlo(
            initial_value,
            w,
            rets.mean().to_numpy(),
            rets.cov().to_numpy(),
            horizon_days,
            paths,
            seed,
        )
    except ValueError as exc:
        raise AppError("invalid_parameters", str(exc), 422) from exc
    final = res.final_values
    hist, edges = np.histogram(final, bins=30)
    return {
        "weights": {i: float(x) for i, x in zip(ids, w, strict=True)},
        "initial_value": initial_value,
        "horizon_days": horizon_days,
        "paths": paths,
        "seed": seed,
        "lookback": lookback,
        "periods_per_year": ppy,
        "estimation_window": {
            "start": rets.index[0].date().isoformat(),
            "end": rets.index[-1].date().isoformat(),
            "observations": int(len(rets)),
        },
        "percentiles": {str(k): v for k, v in res.percentiles.items()},
        "final": {
            "p5": float(np.percentile(final, 5)),
            "p50": float(np.percentile(final, 50)),
            "p95": float(np.percentile(final, 95)),
            "mean": float(final.mean()),
        },
        "probability_of_loss": res.probability_of_loss,
        "histogram": [
            {"from": float(edges[k]), "to": float(edges[k + 1]), "count": int(hist[k])}
            for k in range(len(hist))
        ],
        "assumptions": [
            "Daily returns are drawn from a multivariate normal distribution with the mean and "
            "covariance measured over the look-back window.",
            "Weights are rebalanced daily; no fees, taxes or currency effects.",
            "Real markets have fatter tails than a normal distribution, so extreme losses are "
            "likely understated.",
            "This is a range of simulated outcomes, not a forecast.",
        ],
    }


STRESS_PRESETS: dict[str, dict[str, Any]] = {
    "equity_crash": {
        "label": "Global equity sell-off",
        "description": "Stocks and indices fall 20%, crypto 35%, gold rises 5%.",
        "by_class": {"equity": -0.20, "index": -0.20, "etf": -0.20, "crypto": -0.35},
        "by_metal": {"gold": 0.05, "silver": -0.05},
    },
    "crypto_winter": {
        "label": "Crypto winter",
        "description": "Crypto falls 60%; other assets unchanged.",
        "by_class": {"crypto": -0.60},
        "by_metal": {},
    },
    "rupee_shock": {
        "label": "Rupee falls 10%",
        "description": "USD/INR rises 10%; Indian stocks fall 8%; US assets gain 10% in INR terms.",
        "by_class": {},
        "by_metal": {},
        "india_equity": -0.08,
        "usd_assets_in_inr": 0.10,
    },
}


def run_stress(
    session: Session,
    weights: dict[str, float],
    shocks: dict[str, float] | None,
    preset: str | None,
) -> dict[str, Any]:
    total = sum(weights.values())
    if total <= 0:
        raise AppError("invalid_weights", "Weights must sum to more than 0", 422)
    norm = {k: v / total for k, v in weights.items()}
    applied = dict(shocks or {})
    if preset:
        if preset not in STRESS_PRESETS:
            raise AppError("invalid_preset", f"Unknown scenario {preset!r}", 422)
        p = STRESS_PRESETS[preset]
        for i in norm:
            if i in applied:
                continue
            inst = md.get_instrument(session, i)
            metal = inst.attributes.get("metal")
            if metal and metal in p["by_metal"]:
                applied[i] = p["by_metal"][metal]
            elif inst.asset_class in p["by_class"]:
                applied[i] = p["by_class"][inst.asset_class]
            elif preset == "rupee_shock":
                if inst.region == "india" and inst.asset_class in ("equity", "index"):
                    applied[i] = p["india_equity"]
                elif inst.currency == "USD":
                    applied[i] = p["usd_assets_in_inr"]
    for k, v in applied.items():
        if not -1 <= v <= 5:
            raise AppError("invalid_shock", f"Shock for {k} must be between -100% and +500%", 422)
    result = stress_test(norm, applied)
    return {
        "weights": norm,
        "shocks": applied,
        "contributions": {k: v for k, v in result.items() if k != "total"},
        "total": result["total"],
        "preset": preset,
        "note": "Instant, one-off price moves applied to current weights. Not a prediction.",
    }


# --- metals context ----------------------------------------------------------

GOLD_FUT, SILVER_FUT = "metal:XAU:comex-fut", "metal:XAG:comex-fut"


def metal_context(session: Session, inst: md.InstrumentInfo, period: str) -> dict[str, Any] | None:
    """Gold/silver ratio and how much of an INR return came from USD/INR."""
    if not inst.attributes.get("metal"):
        return None
    start = md.period_start(period, today_utc())
    gold = md.load_bars(session, GOLD_FUT, start)["close"]
    silver = md.load_bars(session, SILVER_FUT, start)["close"]
    ratio = (gold / silver).dropna()
    out: dict[str, Any] = {
        "gold_silver_ratio": round(float(ratio.iloc[-1]), 2) if not ratio.empty else None,
        "gold_silver_ratio_series": _series_points(ratio, 3),
        "inr_decomposition": None,
    }
    if inst.currency == "USD":
        usd = md.total_return_series(md.load_bars(session, inst.id, start)).dropna()
        fx = md.fx_series(session, start).dropna()
        if len(usd) > 1 and len(fx) > 1:
            fx_al = fx.reindex(usd.index.union(fx.index)).sort_index().ffill().reindex(usd.index)
            fx_al = fx_al.dropna()
            usd = usd.reindex(fx_al.index)
            if len(usd) > 1:
                r_usd = float(usd.iloc[-1] / usd.iloc[0] - 1)
                r_fx = float(fx_al.iloc[-1] / fx_al.iloc[0] - 1)
                r_inr = (1 + r_usd) * (1 + r_fx) - 1
                out["inr_decomposition"] = {
                    "usd_return": r_usd,
                    "fx_return": r_fx,
                    "inr_return": r_inr,
                    "explanation": "INR return = (1 + USD return) × (1 + change in USD/INR) − 1.",
                }
    return out
