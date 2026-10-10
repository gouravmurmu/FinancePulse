"""Portfolios: CRUD, ledger validation, valuation, performance, risk, CSV.

Every query filters on the verified user id. The API connects as the table
owner (bypassing RLS), so these filters are what isolate users here; RLS
protects direct access through Supabase's public endpoints.
"""

from __future__ import annotations

import csv
import io
import math
import uuid
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.analytics import metrics as m
from app.analytics import portfolio as pf
from app.analytics.conventions import MIN_OBSERVATIONS, mixed_periods_per_year
from app.core.errors import AppError
from app.data.universe import DEFAULT_BENCHMARK
from app.models import Portfolio, Transaction
from app.services import analytics_service as svc
from app.services import market_data as md

MAX_PORTFOLIOS = 20
MAX_TRANSACTIONS = 2000
HOLDABLE = ("equity", "etf", "crypto", "commodity")
OTHER_SLICE_AFTER = 5  # allocation charts show at most 6 slices
CSV_COLUMNS = ["date", "instrument_id", "side", "quantity", "unit", "price", "fees", "notes"]


# --- lookups -----------------------------------------------------------------


def _not_found() -> AppError:
    return AppError("not_found", "Portfolio not found", 404)


def get_portfolio(session: Session, user_id: uuid.UUID, portfolio_id: uuid.UUID) -> Portfolio:
    p = session.scalar(
        select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
    )
    if p is None:
        raise _not_found()
    return p


def _transactions(session: Session, p: Portfolio) -> list[Transaction]:
    return list(
        session.scalars(
            select(Transaction)
            .where(Transaction.portfolio_id == p.id, Transaction.user_id == p.user_id)
            .order_by(Transaction.trade_date, Transaction.created_at)
        )
    )


def portfolio_out(session: Session, p: Portfolio) -> dict[str, Any]:
    count = session.scalar(
        select(func.count()).select_from(Transaction).where(Transaction.portfolio_id == p.id)
    )
    return {
        "id": p.id,
        "name": p.name,
        "base_currency": p.base_currency,
        "benchmark_id": p.benchmark_id,
        "transaction_count": int(count or 0),
        "created_at": p.created_at,
    }


def list_portfolios(session: Session, user_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(Portfolio).where(Portfolio.user_id == user_id).order_by(Portfolio.created_at)
    ).all()
    return [portfolio_out(session, p) for p in rows]


def _check_benchmark(session: Session, benchmark_id: str | None) -> None:
    if benchmark_id:
        md.get_instrument(session, benchmark_id)


def create_portfolio(
    session: Session,
    user_id: uuid.UUID,
    name: str,
    base_currency: str,
    benchmark_id: str | None,
) -> Portfolio:
    count = session.scalar(
        select(func.count()).select_from(Portfolio).where(Portfolio.user_id == user_id)
    )
    if (count or 0) >= MAX_PORTFOLIOS:
        raise AppError("limit_reached", f"You can have up to {MAX_PORTFOLIOS} portfolios", 422)
    _check_benchmark(session, benchmark_id)
    p = Portfolio(
        user_id=user_id,
        name=name.strip(),
        base_currency=base_currency,
        benchmark_id=benchmark_id
        or DEFAULT_BENCHMARK["india" if base_currency == "INR" else "global"],
    )
    session.add(p)
    _flush_unique(session, "You already have a portfolio with this name")
    session.commit()
    return p


def update_portfolio(session: Session, p: Portfolio, changes: dict[str, Any]) -> Portfolio:
    if "benchmark_id" in changes:
        _check_benchmark(session, changes["benchmark_id"])
    for key in ("name", "base_currency", "benchmark_id"):
        if key in changes and changes[key] is not None:
            setattr(p, key, changes[key].strip() if key == "name" else changes[key])
    _flush_unique(session, "You already have a portfolio with this name")
    session.commit()
    return p


def delete_portfolio(session: Session, p: Portfolio) -> None:
    session.delete(p)
    session.commit()


def _flush_unique(session: Session, message: str) -> None:
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise AppError("conflict", message, 409) from exc


# --- transactions --------------------------------------------------------------


def display_name(inst: md.InstrumentInfo) -> str:
    """Metal reference series stand for physical holdings in a portfolio."""
    metal = inst.attributes.get("metal")
    if inst.asset_class == "commodity" and metal:
        return f"Physical {metal} (COMEX reference)"
    return inst.name


def _validate_instrument(session: Session, instrument_id: str, unit: str) -> md.InstrumentInfo:
    inst = md.get_instrument(session, instrument_id)
    if inst.asset_class not in HOLDABLE or inst.currency not in ("USD", "INR"):
        raise AppError(
            "not_holdable",
            f"{inst.name} can't be held in a portfolio. Indices and FX rates are "
            "reference series; hold an ETF or the constituents instead.",
            422,
        )
    is_metal = inst.asset_class == "commodity"
    if is_metal and unit not in ("troy_oz", "gram"):
        raise AppError(
            "invalid_unit",
            f"{inst.name} is used to value physical metal: enter the weight in grams or "
            "troy ounces. For an ETF holding, pick the ETF instead.",
            422,
        )
    if not is_metal and unit != "unit":
        raise AppError("invalid_unit", f"{inst.name} is held in units (shares or coins)", 422)
    return inst


def _check_ledger(session: Session, p: Portfolio) -> None:
    """Replays the ledger so no sale ever exceeds the holding."""
    try:
        pf.build_positions(_trades(session, p, _transactions(session, p)))
    except pf.LedgerError as exc:
        session.rollback()
        name = display_name(md.get_instrument(session, exc.instrument_id))
        raise AppError("oversold", f"{name}: {exc}.", 422) from exc


def add_transactions(
    session: Session, p: Portfolio, items: list[dict[str, Any]], commit: bool = True
) -> list[Transaction]:
    """Adds all items or none. With commit=False the ledger is validated and
    then rolled back (CSV dry run)."""
    existing = session.scalar(
        select(func.count()).select_from(Transaction).where(Transaction.portfolio_id == p.id)
    )
    if (existing or 0) + len(items) > MAX_TRANSACTIONS:
        raise AppError(
            "limit_reached", f"A portfolio can hold up to {MAX_TRANSACTIONS} transactions", 422
        )
    rows = []
    for it in items:
        inst = _validate_instrument(session, it["instrument_id"], it["unit"])
        rows.append(
            Transaction(
                portfolio_id=p.id,
                user_id=p.user_id,
                instrument_id=inst.id,
                side=it["side"],
                trade_date=it["trade_date"],
                quantity=it["quantity"],
                unit=it["unit"],
                price=it["price"],
                fees=it.get("fees") or 0,
                currency=inst.currency,
                notes=it.get("notes"),
            )
        )
    session.add_all(rows)
    session.flush()
    _check_ledger(session, p)
    if commit:
        session.commit()
    else:
        session.rollback()
    return rows


def update_transaction(
    session: Session, p: Portfolio, tx_id: uuid.UUID, data: dict[str, Any]
) -> Transaction:
    tx = session.scalar(
        select(Transaction).where(
            Transaction.id == tx_id,
            Transaction.portfolio_id == p.id,
            Transaction.user_id == p.user_id,
        )
    )
    if tx is None:
        raise AppError("not_found", "Transaction not found", 404)
    inst = _validate_instrument(session, data["instrument_id"], data["unit"])
    tx.instrument_id = inst.id
    tx.currency = inst.currency
    for key in ("side", "trade_date", "quantity", "unit", "price", "notes"):
        setattr(tx, key, data.get(key))
    tx.fees = data.get("fees") or Decimal(0)
    session.flush()
    _check_ledger(session, p)
    session.commit()
    return tx


def delete_transaction(session: Session, p: Portfolio, tx_id: uuid.UUID) -> None:
    tx = session.scalar(
        select(Transaction).where(
            Transaction.id == tx_id,
            Transaction.portfolio_id == p.id,
            Transaction.user_id == p.user_id,
        )
    )
    if tx is None:
        raise AppError("not_found", "Transaction not found", 404)
    session.delete(tx)
    session.flush()
    _check_ledger(session, p)
    session.commit()


def transaction_out(tx: Transaction, names: dict[str, str]) -> dict[str, Any]:
    return {
        "id": tx.id,
        "instrument_id": tx.instrument_id,
        "name": names.get(tx.instrument_id, tx.instrument_id),
        "side": tx.side,
        "trade_date": tx.trade_date,
        "quantity": float(tx.quantity),
        "unit": tx.unit,
        "price": float(tx.price),
        "fees": float(tx.fees),
        "currency": tx.currency,
        "notes": tx.notes,
    }


def list_transactions(session: Session, p: Portfolio) -> list[dict[str, Any]]:
    names = {i.id: display_name(i) for i in md.list_instruments(session)}
    return [transaction_out(t, names) for t in reversed(_transactions(session, p))]


# --- FX and valuation inputs ---------------------------------------------------


def _fx_to_base(local: str, base: str, usdinr: pd.Series) -> pd.Series | float:
    """Base-currency amount per one unit of local currency, by date."""
    if local == base:
        return 1.0
    if usdinr.empty:
        raise AppError("fx_unavailable", "USD/INR rates are not available yet", 503)
    return usdinr if (local, base) == ("USD", "INR") else 1.0 / usdinr


def _rate_on(series: pd.Series | float, d: date) -> float:
    if isinstance(series, float):
        return series
    s = series.loc[: pd.Timestamp(d)]
    if s.empty:  # trade before the first stored rate: use the earliest one
        return float(series.iloc[0])
    return float(s.iloc[-1])


def _trades(session: Session, p: Portfolio, txs: list[Transaction]) -> list[pf.Trade]:
    usdinr = (
        md.fx_series(session, None) if any(t.currency != p.base_currency for t in txs) else None
    )
    out = []
    for seq, t in enumerate(txs):
        q, price = pf.to_valuation_units(float(t.quantity), float(t.price), t.unit)
        fx = (
            1.0
            if t.currency == p.base_currency
            else _rate_on(_fx_to_base(t.currency, p.base_currency, usdinr), t.trade_date)
        )
        out.append(
            pf.Trade(t.instrument_id, t.side, t.trade_date, q, price, float(t.fees), fx, seq)
        )
    return out


def _f(x: float | None, digits: int = 2) -> float | None:
    if x is None or not math.isfinite(x):
        return None
    return round(x, digits)


# --- summary: holdings, totals, allocation -------------------------------------


def _group(rows: list[dict[str, Any]], key: str, total: float) -> list[dict[str, Any]]:
    sums: dict[str, float] = {}
    for r in rows:
        sums[r[key] or "Other"] = sums.get(r[key] or "Other", 0.0) + r["value_base"]
    ranked = sorted(sums.items(), key=lambda kv: kv[1], reverse=True)
    out = [{"label": k, "value": _f(v), "weight": _f(v / total, 6)} for k, v in ranked]
    if len(out) > OTHER_SLICE_AFTER + 1:
        rest = sum(v for _, v in ranked[OTHER_SLICE_AFTER:])
        out = out[:OTHER_SLICE_AFTER] + [
            {"label": "Other", "value": _f(rest), "weight": _f(rest / total, 6)}
        ]
    return out


ASSET_CLASS_LABEL = {
    "equity": "Stocks",
    "etf": "ETFs",
    "crypto": "Crypto",
    "commodity": "Physical metal",
}


def summary(session: Session, p: Portfolio) -> dict[str, Any]:
    txs = _transactions(session, p)
    today = svc.today_utc()
    base = p.base_currency
    result: dict[str, Any] = {
        "portfolio": portfolio_out(session, p),
        "base_currency": base,
        "holdings": [],
        "closed": [],
        "totals": None,
        "allocation": {"holding": [], "asset_class": [], "currency": [], "sector": []},
        "as_of": None,
        "notes": [
            "Cost basis is weighted average cost; buy fees add to cost, sell fees reduce proceeds.",
            "Market prices are end-of-day closes, not live quotes.",
            "Dividends and corporate actions are not recorded; enter them as transactions.",
        ],
    }
    if not txs:
        return result
    trades = _trades(session, p, txs)
    positions = pf.build_positions(trades)
    usdinr = md.fx_series(session, today - timedelta(days=30))
    rows: list[dict[str, Any]] = []
    closed: list[dict[str, Any]] = []
    as_of: date | None = None
    for iid, pos in positions.items():
        inst = md.get_instrument(session, iid)
        bars = md.load_bars(session, iid, today - timedelta(days=30))
        last = bars["close"].dropna()
        last_date = last.index[-1].date() if not last.empty else None
        fresh = md.freshness(
            inst.asset_class,
            last_date,
            bars["quote_type"].iloc[-1] if not bars.empty else None,
            today,
        )
        fx_now = _rate_on(_fx_to_base(inst.currency, base, usdinr), today)
        unit = next((t.unit for t in txs if t.instrument_id == iid), "unit")
        if pos.quantity <= 0:
            closed.append(
                {
                    "instrument_id": iid,
                    "name": display_name(inst),
                    "realized_base": _f(pos.realized_base),
                    "realized_local": _f(pos.realized_local),
                    "currency": inst.currency,
                }
            )
            continue
        price = float(last.iloc[-1]) if not last.empty else None
        val = pf.value_position(pos, price, fx_now) if price is not None else None
        if last_date and (as_of is None or last_date > as_of):
            as_of = last_date
        display_qty = pos.quantity * pf.TROY_OUNCE_GRAMS if unit == "gram" else pos.quantity
        rows.append(
            {
                "instrument_id": iid,
                "name": display_name(inst),
                "asset_class": inst.asset_class,
                "asset_class_label": ASSET_CLASS_LABEL.get(inst.asset_class, inst.asset_class),
                "sector": inst.attributes.get("sector")
                or ASSET_CLASS_LABEL.get(inst.asset_class, inst.asset_class),
                "currency": inst.currency,
                "unit": unit,
                "quantity": round(display_qty, 8),
                "average_cost": _f((pos.cost_local / display_qty) if display_qty else None, 6),
                "price": _f(
                    price / pf.TROY_OUNCE_GRAMS if price is not None and unit == "gram" else price,
                    6,
                ),
                "cost_local": _f(pos.cost_local),
                "cost_base": _f(pos.cost_base),
                "value_local": _f(val.value_local) if val else None,
                "value_base": val.value_base if val else 0.0,
                "unrealized_local": _f(val.unrealized_local) if val else None,
                "unrealized_base": _f(val.unrealized_base) if val else None,
                "unrealized_pct": _f(val.unrealized_base / pos.cost_base, 6)
                if val and pos.cost_base > 0
                else None,
                "price_effect_base": _f(val.price_effect_base) if val else None,
                "fx_effect_base": _f(val.fx_effect_base) if val else None,
                "realized_base": _f(pos.realized_base),
                "fx_rate": _f(fx_now, 6),
                "freshness": fresh,
                "price_definition": inst.price_definition,
            }
        )
    total_value = sum(r["value_base"] for r in rows)
    for r in rows:
        r["weight"] = _f(r["value_base"] / total_value, 6) if total_value > 0 else None
        r["value_base"] = _f(r["value_base"])
    rows.sort(key=lambda r: r["value_base"] or 0, reverse=True)
    cost = sum(r["cost_base"] or 0 for r in rows)
    unrealized = sum(r["unrealized_base"] or 0 for r in rows)
    realized = sum(pos.realized_base for pos in positions.values())
    fees_base = sum(t.fees * t.fx for t in trades)
    result.update(
        holdings=rows,
        closed=closed,
        as_of=as_of.isoformat() if as_of else None,
        totals={
            "value": _f(total_value),
            "cost": _f(cost),
            "unrealized": _f(unrealized),
            "unrealized_pct": _f(unrealized / cost, 6) if cost > 0 else None,
            "realized": _f(realized),
            "total_pnl": _f(unrealized + realized),
            "price_effect": _f(sum(r["price_effect_base"] or 0 for r in rows)),
            "fx_effect": _f(sum(r["fx_effect_base"] or 0 for r in rows)),
            "fees": _f(fees_base),
        },
    )
    if total_value > 0:
        valued = [r for r in rows if r["value_base"]]
        named = [{**r, "label": r["name"]} for r in valued]
        result["allocation"] = {
            "holding": _group(named, "label", total_value),
            "asset_class": _group(valued, "asset_class_label", total_value),
            "currency": _group(valued, "currency", total_value),
            "sector": _group(valued, "sector", total_value),
        }
    return result


# --- performance and risk ------------------------------------------------------


def _calendar(start: date, end: date, asset_classes: list[str]) -> pd.DatetimeIndex:
    if asset_classes and all(a == "crypto" for a in asset_classes):
        return pd.date_range(start, end, freq="D")
    return pd.bdate_range(start, end)


def performance(session: Session, p: Portfolio, period: str) -> dict[str, Any]:
    txs = _transactions(session, p)
    if not txs:
        raise AppError("empty_portfolio", "Add a transaction to see performance", 422)
    today = svc.today_utc()
    trades = _trades(session, p, txs)
    ids = sorted({t.instrument_id for t in trades})
    insts = {i: md.get_instrument(session, i) for i in ids}
    first = min(t.trade_date for t in trades)
    cal = _calendar(first, today, [insts[i].asset_class for i in ids])
    usdinr = md.fx_series(session, first - timedelta(days=10))
    prices = pd.DataFrame(
        {i: md.load_bars(session, i, first - timedelta(days=10))["close"] for i in ids}
    )
    fx_cols = {}
    for i in ids:
        rate = _fx_to_base(insts[i].currency, p.base_currency, usdinr)
        fx_cols[i] = rate if isinstance(rate, pd.Series) else pd.Series(rate, index=cal)
    fx = pd.DataFrame(fx_cols)
    full_index = prices.index.union(fx.index).union(cal)
    prices = prices.reindex(full_index).sort_index().ffill()
    fx = fx.reindex(full_index).sort_index().ffill().bfill()
    series = pf.daily_series(trades, prices, fx, cal)

    start = md.period_start(period, today)
    rets = series.returns if start is None else series.returns.loc[pd.Timestamp(start) :]
    if rets.empty:
        rets = series.returns
    growth = 100.0 * (1.0 + rets).cumprod()
    # Anchor at 100 on the day before the window so the first return shows.
    anchor = rets.index[0] - pd.Timedelta(days=1)
    growth = pd.concat([pd.Series([100.0], index=[anchor]), growth])
    ppy = mixed_periods_per_year([insts[i].asset_class for i in ids])

    bench_id = p.benchmark_id
    bench_points: list[dict[str, Any]] = []
    bench_return = None
    if bench_id:
        b = md.load_bars(session, bench_id, anchor.date() - timedelta(days=10))["close"].dropna()
        b = b.reindex(b.index.union(growth.index)).sort_index().ffill().reindex(growth.index)
        if b.notna().any():
            b = b.bfill()
            bench = 100.0 * b / float(b.iloc[0])
            bench_points = svc._series_points(bench, 4)
            bench_return = float(bench.iloc[-1] / 100.0 - 1)

    dd = m.max_drawdown(growth)
    vol = m.annualized_volatility(rets, ppy) if len(rets) >= MIN_OBSERVATIONS else None
    metrics = {
        "time_weighted_return": float(growth.iloc[-1] / 100.0 - 1),
        "benchmark_return": bench_return,
        "volatility": vol,
        "sharpe": m.sharpe_ratio(rets, ppy) if len(rets) >= MIN_OBSERVATIONS else None,
        "max_drawdown": dd.value if dd else None,
        "var": m.historical_var(rets, 0.95) if len(rets) >= MIN_OBSERVATIONS else None,
        "beta": None,
    }
    if bench_points and len(rets) >= MIN_OBSERVATIONS:
        bser = pd.Series({pd.Timestamp(x["date"]): x["value"] for x in bench_points})
        metrics["beta"] = m.beta(rets, m.simple_returns(bser))

    # Risk and correlation of current holdings over the last year.
    held = [i for i in ids if series.quantities[i].iloc[-1] > 0]
    risk_rows: list[dict[str, Any]] = []
    corr: dict[str, Any] | None = None
    if held:
        last_val = {
            i: float(series.quantities[i].iloc[-1] * prices[i].reindex(cal).ffill().iloc[-1])
            * float(fx[i].reindex(cal).ffill().iloc[-1])
            for i in held
        }
        weights = pd.Series(last_val)
        year = prices[held].loc[pd.Timestamp(today - timedelta(days=365)) :]
        year_fx = fx[held].loc[year.index]
        hr = (year * year_fx).reindex(cal.intersection(year.index)).pct_change().dropna(how="all")
        hr = hr.dropna()
        rc = (
            pf.risk_contributions(weights, hr)
            if len(hr) >= MIN_OBSERVATIONS and len(held) > 1
            else None
        )
        total_w = weights.sum()
        for i in held:
            risk_rows.append(
                {
                    "instrument_id": i,
                    "name": display_name(insts[i]),
                    "weight": _f(weights[i] / total_w, 6) if total_w > 0 else None,
                    "volatility": _f(
                        m.annualized_volatility(hr[i], ppy)
                        if i in hr and len(hr) >= MIN_OBSERVATIONS
                        else None,
                        6,
                    ),
                    "risk_contribution": _f(float(rc[i]), 6)
                    if rc is not None and i in rc
                    else None,
                }
            )
        if len(held) > 1 and len(hr) >= MIN_OBSERVATIONS:
            c = m.correlation_matrix(hr[held])
            corr = {
                "ids": held,
                "names": [display_name(insts[i]) for i in held],
                "matrix": [[round(float(c.loc[a, b]), 4) for b in held] for a in held],
            }

    values = series.value.loc[rets.index[0] :]
    return {
        "period": period,
        "base_currency": p.base_currency,
        "start": rets.index[0].date().isoformat(),
        "end": rets.index[-1].date().isoformat(),
        "observations": int(len(rets)),
        "periods_per_year": ppy,
        "portfolio": svc._series_points(growth, 4),
        "benchmark": {
            "instrument_id": bench_id,
            "name": md.get_instrument(session, bench_id).name if bench_id else None,
            "points": bench_points,
        },
        "value": svc._series_points(values, 2),
        "drawdown": svc._series_points(m.drawdown_series(growth), 4),
        "metrics": metrics,
        "risk": risk_rows,
        "correlation": corr,
        "insight": _insight(metrics, period),
        "assumptions": [
            "Time-weighted return: deposits and withdrawals don't count as performance.",
            "Holdings are valued at each day's close; missing days carry the last close forward.",
            f"Volatility and VaR use daily returns, annualized with {ppy} periods per year; "
            "VaR is one-day, 95%, reported as a positive loss.",
            "The benchmark is its price index in its own currency (no dividends).",
            "Risk contribution: each holding's share of portfolio variance over the last year.",
        ],
        "warning": None
        if len(rets) >= MIN_OBSERVATIONS
        else f"Only {len(rets)} days of history; volatility, Sharpe and VaR need "
        f"at least {MIN_OBSERVATIONS}.",
    }


def _insight(metrics: dict[str, Any], period: str) -> str | None:
    r = metrics["time_weighted_return"]
    b = metrics["benchmark_return"]
    words = svc.PERIOD_WORDS.get(period, period)
    if r is None:
        return None
    text = f"Your portfolio returned {r:+.1%} {words}"
    if b is not None:
        diff = r - b
        if abs(diff) < 0.0005:
            text += ", in line with its benchmark"
        else:
            text += f", {abs(diff):.1%} {'ahead of' if diff > 0 else 'behind'} its benchmark"
    return text + "."


def stress(
    session: Session, p: Portfolio, preset: str | None, shocks: dict[str, float] | None
) -> dict[str, Any]:
    s = summary(session, p)
    values = {h["instrument_id"]: h["value_base"] for h in s["holdings"] if h["value_base"]}
    if not values:
        raise AppError("empty_portfolio", "Add holdings to run a stress test", 422)
    res = svc.run_stress(session, values, shocks, preset)
    total = s["totals"]["value"]
    res["value"] = total
    res["pnl"] = _f(total * res["total"])
    res["contribution_amounts"] = {k: _f(total * v) for k, v in res["contributions"].items()}
    res["base_currency"] = p.base_currency
    return res


# --- CSV -----------------------------------------------------------------------


def export_csv(session: Session, p: Portfolio) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(CSV_COLUMNS + ["currency"])
    for t in _transactions(session, p):
        w.writerow(
            [
                t.trade_date.isoformat(),
                t.instrument_id,
                t.side,
                format(t.quantity.normalize(), "f"),
                t.unit,
                format(t.price.normalize(), "f"),
                format(t.fees.normalize(), "f"),
                t.notes or "",
                t.currency,
            ]
        )
    return buf.getvalue()


def _dec(value: str, field: str, line: int) -> Decimal:
    try:
        d = Decimal(value.strip().replace(",", "")) if value.strip() else Decimal(0)
    except InvalidOperation as exc:
        raise ValueError(f"line {line}: {field} {value!r} is not a number") from exc
    if not d.is_finite():
        raise ValueError(f"line {line}: {field} must be a number")
    return d


def parse_csv(session: Session, text: str) -> list[dict[str, Any]]:
    """Parse and validate every row; raises AppError listing all problems."""
    reader = csv.DictReader(io.StringIO(text.strip()))
    header = [h.strip().lower() for h in (reader.fieldnames or [])]
    missing = [c for c in ("date", "instrument_id", "side", "quantity", "price") if c not in header]
    if missing:
        raise AppError(
            "invalid_csv",
            f"Missing column(s): {', '.join(missing)}. Expected: {', '.join(CSV_COLUMNS)}",
            422,
        )
    known = {i.id for i in md.list_instruments(session)}
    items: list[dict[str, Any]] = []
    errors: list[str] = []
    today = svc.today_utc()
    for n, raw in enumerate(reader, start=2):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        try:
            d = date.fromisoformat(row["date"])
            if d > today:
                raise ValueError(f"line {n}: date {d} is in the future")
            iid = row["instrument_id"]
            if iid not in known:
                raise ValueError(f"line {n}: unknown instrument {iid!r}")
            side = row["side"].lower()
            if side not in ("buy", "sell"):
                raise ValueError(f"line {n}: side must be buy or sell")
            qty = _dec(row["quantity"], "quantity", n)
            price = _dec(row["price"], "price", n)
            fees = _dec(row.get("fees", ""), "fees", n)
            if qty <= 0 or price < 0 or fees < 0:
                raise ValueError(
                    f"line {n}: quantity must be positive; price and fees not negative"
                )
            unit = (row.get("unit") or "").lower() or (
                "troy_oz" if iid.startswith("metal:") else "unit"
            )
            items.append(
                {
                    "instrument_id": iid,
                    "side": side,
                    "trade_date": d,
                    "quantity": qty,
                    "unit": unit,
                    "price": price,
                    "fees": fees,
                    "notes": (row.get("notes") or None) and row["notes"][:200],
                }
            )
        except (ValueError, KeyError) as exc:
            errors.append(str(exc) if isinstance(exc, ValueError) else f"line {n}: bad row")
        if len(errors) >= 20:
            break
    if errors:
        raise AppError("invalid_csv", "Some rows could not be imported", 422, errors)
    if not items:
        raise AppError("invalid_csv", "The file has no transactions", 422)
    return items
