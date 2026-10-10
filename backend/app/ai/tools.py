"""Tools the assistant can call. Every number comes from these deterministic
backend functions; the model only chooses tools and writes the explanation.

Each result is kept small and carries its source and as-of time so the answer
can cite them.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.services import alert_service, forecast_service, fundamentals_service, news_service
from app.services import analytics_service as svc
from app.services import market_data as md
from app.services import portfolio_service as ps

PERIODS = ["1M", "3M", "6M", "YTD", "1Y", "3Y", "5Y"]
PRICE_SOURCE = "Daily closes stored by MarketPulse (Yahoo Finance via yfinance)"


@dataclass
class ToolContext:
    session: Session
    user_id: uuid.UUID


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    run: Callable[[ToolContext, dict[str, Any]], dict[str, Any]]

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def _r(x: Any, digits: int = 4) -> Any:
    return round(x, digits) if isinstance(x, float) else x


def _inst(ctx: ToolContext, args: dict[str, Any]) -> md.InstrumentInfo:
    return md.get_instrument(ctx.session, str(args.get("instrument_id", "")))


def _id_param(desc: str = "Canonical instrument ID, e.g. eq:us:AAPL") -> dict[str, Any]:
    return {"instrument_id": {"type": "string", "description": desc}}


def search_instruments(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    found = md.search_instruments(ctx.session, str(args.get("query", "")), 6)
    return {
        "results": [
            {"instrument_id": i.id, "name": i.name, "asset_class": i.asset_class} for i in found
        ],
        "note": "Only these tracked instruments have data." if found else "No match.",
    }


def get_quote(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    inst = _inst(ctx, args)
    q = svc.quote(ctx.session, inst, "1D", None)
    return {
        "instrument_id": inst.id,
        "name": inst.name,
        "asset_class": inst.asset_class,
        "price": q["price"],
        "currency": q["currency"],
        "price_definition": inst.price_definition,
        "change_pct_1d": _r(q["change_pct"]),
        "as_of": q["as_of"],
        "freshness": q["freshness"],
        "source": PRICE_SOURCE,
    }


def get_risk(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    inst = _inst(ctx, args)
    period = str(args["period"]) if args.get("period") in PERIODS else "1Y"
    r = svc.instrument_risk(ctx.session, inst, period, None, 0.95)
    keep = (
        "total_return",
        "cagr",
        "volatility",
        "sharpe",
        "max_drawdown",
        "max_drawdown_trough",
        "var",
        "beta",
    )
    return {
        "instrument_id": inst.id,
        "name": inst.name,
        "period": period,
        "metrics": {k: _r(r["metrics"].get(k)) for k in keep},
        "benchmark_id": r["benchmark_id"],
        "risk_level": r["risk_level"],
        "observations": r["observations"],
        "assumptions": r["assumptions"],
        "warning": r.get("warning"),
        "source": PRICE_SOURCE,
    }


def compare_assets(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    ids = [str(i) for i in (args.get("instrument_ids") or [])][:5]
    if len(ids) < 2:
        raise AppError("bad_request", "Give at least two instrument IDs", 422)
    period = str(args["period"]) if args.get("period") in PERIODS else "1Y"
    rows = []
    for i in ids:
        r = get_risk(ctx, {"instrument_id": i, "period": period})
        rows.append({"instrument_id": i, "name": r["name"], **r["metrics"]})
    return {
        "period": period,
        "rows": rows,
        "note": "Returns are in each asset's own currency.",
        "source": PRICE_SOURCE,
    }


def get_fundamentals(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    inst = _inst(ctx, args)
    f = fundamentals_service.fundamentals(ctx.session, inst)
    if not f.get("available", True) or not f.get("years"):
        return {"instrument_id": inst.id, "available": False, "reason": f.get("reason")}
    keep = (
        "fiscal_year",
        "period_end",
        "revenue",
        "net_income",
        "operating_margin",
        "net_margin",
        "free_cash_flow",
        "revenue_growth",
    )
    return {
        "instrument_id": inst.id,
        "currency": f["currency"],
        "years": [{k: _r(y.get(k)) for k in keep} for y in f["years"][-3:]],
        "last_filed": f.get("last_filed"),
        "source": f["source"],
    }


def get_news(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    inst = _inst(ctx, args)
    n = news_service.instrument_news(ctx.session, inst, 8)
    return {
        "instrument_id": inst.id,
        "coverage_note": n["coverage_note"],
        "headlines": [
            {
                "headline": a["headline"],
                "source": a["source"],
                "published_at": a["published_at"].isoformat(),
                "url": a["url"],
                "tone": a["sentiment"]["label"] if a["sentiment"] else None,
            }
            for a in n["articles"]
        ],
        "source": "Finnhub headlines; tone from FinBERT (headline only)",
    }


def get_forecast(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    inst = _inst(ctx, args)
    f = forecast_service.latest(ctx.session, inst)
    if not f["available"]:
        return {"instrument_id": inst.id, "available": False, "reason": f["reason"]}
    return {
        "instrument_id": inst.id,
        "horizons": [
            {
                "horizon_trading_days": h["horizon_days"],
                "as_of": h["as_of"],
                "beats_no_change_baseline": h["beats_baseline"],
                "model": h["best_model_label"],
                "point": _r(h["point"]) if h["beats_baseline"] else None,
                "range_80pct": [_r(h["lower"]), _r(h["upper"])],
                "skill_vs_baseline": _r(h["skill"]),
            }
            for h in f["horizons"]
        ],
        "source": "MarketPulse baseline forecasts, walk-forward tested (docs/MODELS.md)",
    }


def get_anomalies(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    inst = _inst(ctx, args)
    rows = alert_service.list_anomalies(ctx.session, inst.id, 180, 10)
    return {
        "instrument_id": inst.id,
        "flags": [
            {"date": a["observed_at"], "kind": a["label"], "detail": a["description"]} for a in rows
        ],
        "note": "Statistical flags (robust z-score), not verified news catalysts.",
    }


def _portfolio(ctx: ToolContext, args: dict[str, Any]) -> Any:
    raw = args.get("portfolio_id")
    if raw:
        try:
            return ps.get_portfolio(ctx.session, ctx.user_id, uuid.UUID(str(raw)))
        except ValueError as exc:
            raise AppError("not_found", "Portfolio not found", 404) from exc
    mine = ps.list_portfolios(ctx.session, ctx.user_id)
    if not mine:
        raise AppError("not_found", "This user has no portfolios yet", 404)
    return ps.get_portfolio(ctx.session, ctx.user_id, mine[0]["id"])


def get_portfolio(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    p = _portfolio(ctx, args)
    s = ps.summary(ctx.session, p)
    t = s["totals"]
    return {
        "portfolio": p.name,
        "base_currency": p.base_currency,
        "totals": {
            k: _r(t.get(k))
            for k in ("value", "cost", "unrealized", "unrealized_pct", "realized", "fx_effect")
        },
        "holdings": [
            {
                "name": h["name"],
                "instrument_id": h["instrument_id"],
                "weight": _r(h["weight"]),
                "value_base": _r(h["value_base"], 2),
                "unrealized_pct": _r(h["unrealized_pct"]),
            }
            for h in sorted(s["holdings"], key=lambda h: -(h["weight"] or 0))[:10]
        ],
        "allocation_by_asset_class": [
            {"label": a["label"], "weight": _r(a["weight"])}
            for a in s["allocation"].get("asset_class", [])
        ],
        "source": "Your recorded transactions valued at stored daily closes",
    }


def stress_portfolio(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    p = _portfolio(ctx, args)
    preset = str(args.get("preset") or "")
    if preset not in svc.STRESS_PRESETS:
        return {
            "error": "Unknown scenario",
            "available_presets": {k: v["label"] for k, v in svc.STRESS_PRESETS.items()},
        }
    r = ps.stress(ctx.session, p, preset, None)
    return {
        "portfolio": p.name,
        "scenario": svc.STRESS_PRESETS[preset]["label"],
        "scenario_description": svc.STRESS_PRESETS[preset]["description"],
        "total_change": _r(r["total"]),
        "pnl": _r(r["pnl"], 2),
        "base_currency": r["base_currency"],
        "note": "Hypothetical shocks applied to today's holdings; not a forecast.",
    }


TOOLS: list[Tool] = [
    Tool(
        "search_instruments",
        "Find tracked instruments by name, ticker or alias. Use first when the user names an "
        "asset and you do not know its instrument_id.",
        {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        search_instruments,
    ),
    Tool(
        "get_quote",
        "Latest stored daily close, 1-day change and data freshness for one instrument.",
        {"type": "object", "properties": _id_param(), "required": ["instrument_id"]},
        get_quote,
    ),
    Tool(
        "get_risk",
        "Return and risk metrics over a period: total return, CAGR, volatility, Sharpe, max "
        "drawdown, 1-day 95% VaR, beta vs benchmark.",
        {
            "type": "object",
            "properties": {**_id_param(), "period": {"type": "string", "enum": PERIODS}},
            "required": ["instrument_id"],
        },
        get_risk,
    ),
    Tool(
        "compare_assets",
        "Compare 2 to 5 instruments on the same return and risk metrics.",
        {
            "type": "object",
            "properties": {
                "instrument_ids": {"type": "array", "items": {"type": "string"}},
                "period": {"type": "string", "enum": PERIODS},
            },
            "required": ["instrument_ids"],
        },
        compare_assets,
    ),
    Tool(
        "get_fundamentals",
        "Annual financials from SEC filings (US companies only): revenue, net income, "
        "margins, free cash flow, growth.",
        {"type": "object", "properties": _id_param(), "required": ["instrument_id"]},
        get_fundamentals,
    ),
    Tool(
        "get_news",
        "Recent headlines with source links and FinBERT tone for one instrument.",
        {"type": "object", "properties": _id_param(), "required": ["instrument_id"]},
        get_news,
    ),
    Tool(
        "get_forecast",
        "Stored baseline forecasts and whether any model beat the no-change baseline.",
        {"type": "object", "properties": _id_param(), "required": ["instrument_id"]},
        get_forecast,
    ),
    Tool(
        "get_anomalies",
        "Statistical anomaly flags (unusual moves, volume, volatility, correlation) in the "
        "last 6 months.",
        {"type": "object", "properties": _id_param(), "required": ["instrument_id"]},
        get_anomalies,
    ),
    Tool(
        "get_portfolio",
        "The signed-in user's portfolio: totals, P&L, top holdings and allocation. Omit "
        "portfolio_id to use their first portfolio.",
        {"type": "object", "properties": {"portfolio_id": {"type": "string"}}},
        get_portfolio,
    ),
    Tool(
        "stress_portfolio",
        "Apply a preset stress scenario to the user's portfolio.",
        {
            "type": "object",
            "properties": {
                "portfolio_id": {"type": "string"},
                "preset": {
                    "type": "string",
                    "enum": ["equity_crash", "crypto_winter", "rupee_shock"],
                },
            },
            "required": ["preset"],
        },
        stress_portfolio,
    ),
]

BY_NAME = {t.name: t for t in TOOLS}


def run_tool(ctx: ToolContext, name: str, args: dict[str, Any]) -> dict[str, Any]:
    tool = BY_NAME.get(name)
    if tool is None:
        return {"error": f"Unknown tool {name}"}
    try:
        return tool.run(ctx, args)
    except AppError as exc:
        return {"error": exc.message}
