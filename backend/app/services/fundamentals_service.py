"""Annual fundamentals table with derived ratios."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Fundamental
from app.providers.sec import CONCEPTS
from app.services import market_data as md


def _ratio(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return a / b


def _growth(cur: float | None, prev: float | None) -> float | None:
    # Growth from a negative base is not meaningful.
    if cur is None or prev is None or prev <= 0:
        return None
    return cur / prev - 1


def fundamentals(session: Session, inst: md.InstrumentInfo) -> dict[str, Any]:
    base: dict[str, Any] = {
        "instrument_id": inst.id,
        "currency": "USD",
        "source": "SEC EDGAR company facts (10-K filings)",
        "years": [],
        "last_filed": None,
        "retrieved_at": None,
    }
    if not inst.attributes.get("cik"):
        return {
            **base,
            "available": False,
            "reason": "Fundamentals are only available for US-listed companies, "
            "from their SEC filings.",
        }
    rows = session.scalars(select(Fundamental).where(Fundamental.instrument_id == inst.id)).all()
    if not rows:
        return {
            **base,
            "available": False,
            "reason": "Financials for this company have not been loaded yet.",
        }

    # Group by fiscal-year end. Balance-sheet instants share the year-end date
    # of the matching flow period.
    by_end: dict[Any, dict[str, Any]] = {}
    for r in rows:
        row = by_end.setdefault(
            r.period_end, {"period_end": r.period_end, "fiscal_year": r.fiscal_year}
        )
        row[r.concept] = float(r.value)
    years = [by_end[k] for k in sorted(by_end)]
    years = [y for y in years if "revenue" in y or "net_income" in y][-5:]

    out = []
    prev: dict[str, Any] | None = None
    prev_end = None
    for y in years:
        v = {c: y.get(c) for c in CONCEPTS}
        # Growth only between consecutive fiscal years (gaps in filings happen).
        if prev_end is None or not 330 <= (y["period_end"] - prev_end).days <= 400:
            prev = None
        ocf, capex = v["operating_cash_flow"], v["capex"]
        out.append(
            {
                "fiscal_year": y["fiscal_year"],
                "period_end": y["period_end"].isoformat(),
                **v,
                "gross_margin": _ratio(v["gross_profit"], v["revenue"]),
                "operating_margin": _ratio(v["operating_income"], v["revenue"]),
                "net_margin": _ratio(v["net_income"], v["revenue"]),
                "free_cash_flow": ocf - capex if ocf is not None and capex is not None else None,
                "debt_to_equity": _ratio(v["long_term_debt"], v["equity"])
                if (v["equity"] or 0) > 0
                else None,
                "revenue_growth": _growth(v["revenue"], prev.get("revenue") if prev else None),
                "net_income_growth": _growth(
                    v["net_income"], prev.get("net_income") if prev else None
                ),
            }
        )
        prev = v
        prev_end = y["period_end"]
    return {
        **base,
        "available": bool(out),
        "reason": None if out else "No annual figures were found in this company's filings.",
        "years": out,
        "last_filed": max(r.filed for r in rows).isoformat(),
        "retrieved_at": max(r.retrieved_at for r in rows).isoformat(),
    }
