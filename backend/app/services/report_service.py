"""PDF and CSV reports built from the same services as the API.

Reports are generated on demand and not stored. Every figure carries its
source and as-of date, and every PDF ends with the methodology and the
research-only disclaimer.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from fpdf import FPDF
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Portfolio
from app.services import alert_service, forecast_service, fundamentals_service, news_service
from app.services import analytics_service as svc
from app.services import market_data as md
from app.services import portfolio_service as ps

DISCLAIMER = (
    "MarketPulse is a research tool, not investment advice. Prices are end-of-day closes "
    "and may be delayed. Past performance and statistical estimates do not predict future "
    "results. Check figures against the original sources before acting on them."
)
PRICE_SOURCE = "Daily closes stored by MarketPulse (Yahoo Finance via yfinance)"

ACCENT = (13, 148, 136)
MUTED = (100, 110, 120)
RULE = (220, 224, 228)
POSITIVE = (22, 128, 61)
NEGATIVE = (190, 40, 40)

# The built-in PDF fonts only cover Latin-1, so map common typography to it.
_LATIN1 = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "−": "-",
        "…": "...",
        "₹": "Rs ",
        " ": " ",
        "•": "-",
    }
)


def _t(text: Any) -> str:
    s = str(text).translate(_LATIN1)
    return s.encode("latin-1", "replace").decode("latin-1")


def pct(v: float | None, signed: bool = True, digits: int = 1) -> str:
    if v is None:
        return "n/a"
    return f"{v * 100:+.{digits}f}%" if signed else f"{v * 100:.{digits}f}%"


def num(v: float | None, digits: int = 2) -> str:
    return "n/a" if v is None else f"{v:,.{digits}f}"


def money(v: float | None, ccy: str, digits: int = 2) -> str:
    return "n/a" if v is None else f"{ccy} {v:,.{digits}f}"


def price_digits(v: float | None) -> int:
    if v is None:
        return 2
    return 2 if abs(v) >= 1 else 6


class Report(FPDF):
    def __init__(self, title: str) -> None:
        super().__init__(format="A4")
        self.report_title = _t(title)
        self.generated = datetime.now(UTC)
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(16, 16, 16)
        self.set_title(self.report_title)
        self.set_author("MarketPulse")
        self.set_creator("MarketPulse")
        self.add_page()

    @property
    def width(self) -> float:
        return float(self.w - self.l_margin - self.r_margin)

    def header(self) -> None:
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*ACCENT)
        self.cell(0, 5, "MarketPulse", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*RULE)
        self.line(self.l_margin, self.get_y() + 1, self.w - self.r_margin, self.get_y() + 1)
        self.ln(4)
        self.set_text_color(0, 0, 0)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*MUTED)
        stamp = self.generated.strftime("%d %b %Y %H:%M UTC")
        self.cell(0, 4, _t(f"{self.report_title} - generated {stamp}"), align="L")
        self.set_x(self.l_margin)
        self.cell(0, 4, f"Page {self.page_no()}/{{nb}}", align="R")

    def title_block(self, title: str, subtitle: str) -> None:
        self.set_font("Helvetica", "B", 18)
        self.multi_cell(0, 8, _t(title), new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*MUTED)
        self.multi_cell(0, 4.5, _t(subtitle), align="L", new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(3)

    def h2(self, text: str) -> None:
        if self.get_y() > self.h - 50:
            self.add_page()
        self.ln(3)
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 7, _t(text), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def para(self, text: str, size: float = 9.5, muted: bool = False) -> None:
        self.set_font("Helvetica", "", size)
        if muted:
            self.set_text_color(*MUTED)
        self.multi_cell(0, size * 0.5, _t(text), align="L", new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(1)

    def bullets(self, items: Sequence[str], size: float = 8.5, muted: bool = True) -> None:
        self.set_font("Helvetica", "", size)
        if muted:
            self.set_text_color(*MUTED)
        for item in items:
            self.set_x(self.l_margin + 2)
            self.multi_cell(
                self.width - 2,
                size * 0.5,
                _t(f"- {item}"),
                align="L",
                new_x="LMARGIN",
                new_y="NEXT",
            )
        self.set_text_color(0, 0, 0)
        self.ln(1)

    def grid(
        self,
        headers: Sequence[str],
        rows: Sequence[Sequence[Any]],
        widths: Sequence[float],
        align: str | None = None,
    ) -> None:
        """Simple table; `align` is one letter per column (L or R)."""
        total = sum(widths)
        cols = [w * self.width / total for w in widths]
        aligns = align or "L" + "R" * (len(headers) - 1)
        if self.get_y() + 6 * min(len(rows) + 1, 4) > self.h - 24:
            self.add_page()
        self.set_font("Helvetica", "B", 8.5)
        self.set_text_color(*MUTED)
        for h, w, a in zip(headers, cols, aligns, strict=True):
            self.cell(w, 6, _t(h), align=a)
        self.ln()
        self.set_text_color(0, 0, 0)
        self.set_font("Helvetica", "", 8.5)
        self.set_draw_color(*RULE)
        for row in rows:
            if self.get_y() > self.h - 24:
                self.add_page()
            self.line(self.l_margin, self.get_y(), self.l_margin + self.width, self.get_y())
            for v, w, a in zip(row, cols, aligns, strict=True):
                text = _t(v)
                while text and self.get_string_width(text) > w - 1.5:
                    text = text[:-2] + "…".translate(_LATIN1)[:1]
                self.cell(w, 6, text, align=a)
            self.ln()
        self.ln(2)

    def line_chart(
        self,
        series: Sequence[tuple[str, Sequence[float], tuple[int, int, int]]],
        labels: tuple[str, str],
        height: float = 48,
        fmt: Any = num,
    ) -> None:
        """Lines over a shared y-axis. labels are the first and last dates."""
        values = [v for _, s, _ in series for v in s]
        if len(values) < 2:
            return
        if self.get_y() + height + 14 > self.h - 18:
            self.add_page()
        x0, y0 = self.l_margin + 18, self.get_y() + 2
        w, h = self.width - 18, height
        lo, hi = min(values), max(values)
        span = (hi - lo) or 1.0
        self.set_draw_color(*RULE)
        self.set_line_width(0.2)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*MUTED)
        for frac in (0.0, 0.5, 1.0):
            y = y0 + h - frac * h
            self.line(x0, y, x0 + w, y)
            self.set_xy(self.l_margin, y - 2)
            self.cell(17, 4, _t(fmt(lo + frac * span)), align="R")
        for _, s, color in series:
            if len(s) < 2:
                continue
            pts = [
                (x0 + i * w / (len(s) - 1), y0 + h - (v - lo) / span * h) for i, v in enumerate(s)
            ]
            self.set_draw_color(*color)
            self.set_line_width(0.45)
            self.polyline(pts)
        self.set_line_width(0.2)
        self.set_xy(x0, y0 + h + 1)
        self.cell(w / 2, 4, _t(labels[0]))
        self.cell(w / 2, 4, _t(labels[1]), align="R")
        self.ln(5)
        if len(series) > 1:
            self.set_x(x0)
            for name, _, color in series:
                self.set_fill_color(*color)
                self.rect(self.get_x(), self.get_y() + 1.5, 4, 1.2, style="F")
                self.set_x(self.get_x() + 5)
                self.cell(self.get_string_width(_t(name)) + 6, 4, _t(name))
            self.ln(5)
        self.set_text_color(0, 0, 0)
        self.set_draw_color(*RULE)

    def disclaimer(self, methodology: Sequence[str], sources: Sequence[str]) -> None:
        self.h2("Methodology and sources")
        self.bullets(methodology)
        self.bullets([f"Source: {s}" for s in sources])
        self.ln(2)
        self.set_fill_color(245, 247, 248)
        self.set_font("Helvetica", "I", 8.5)
        self.multi_cell(0, 4.5, _t(DISCLAIMER), align="L", fill=True, padding=2)

    def output_bytes(self) -> bytes:
        return bytes(self.output())


def _chart_points(points: list[dict[str, Any]], key: str = "close") -> list[float]:
    vals = [float(p[key]) for p in points if p.get(key) is not None]
    step = max(1, len(vals) // 260)
    return vals[::step] + ([vals[-1]] if vals and (len(vals) - 1) % step else [])


# --- asset report ---------------------------------------------------------------


def asset_pdf(session: Session, instrument_id: str) -> bytes:
    inst = md.get_instrument(session, instrument_id)
    hist = svc.history(session, inst, "1Y", None)
    if not hist["bars"]:
        raise AppError("no_data", f"No price history for {inst.name} yet", 404)
    q = svc.quote(session, inst, "1D", None)
    risk = svc.instrument_risk(session, inst, "1Y", None, 0.95)
    ccy = q["currency"]
    bars = hist["bars"]

    pdf = Report(f"{inst.name} report")
    pdf.alias_nb_pages()
    pdf.title_block(
        f"{inst.name}",
        f"{inst.id} - {inst.asset_class} - {inst.exchange or ''} - {inst.price_definition}. "
        f"Data as of {q['as_of']}.",
    )

    pdf.h2("Price")
    digits = price_digits(q["price"])
    first = bars[0]["close"]
    last = bars[-1]["close"]
    pdf.para(
        f"Last close {money(q['price'], ccy, digits)} on {q['as_of']} "
        f"({pct(q['change_pct'])} on the day). Over the past year the price moved from "
        f"{money(first, ccy, digits)} to {money(last, ccy, digits)} "
        f"({pct(last / first - 1 if first else None)}, price only)."
    )
    pdf.line_chart(
        [("Close", _chart_points(bars), ACCENT)],
        (bars[0]["date"], bars[-1]["date"]),
        fmt=lambda v: f"{v:,.{digits}f}",
    )

    pdf.h2("Return and risk, past year")
    mt = risk["metrics"]
    rows = [
        ("Total return", pct(mt["total_return"]), "Change including dividends where available"),
        ("Annualised volatility", pct(mt["volatility"], False), "How widely daily returns swing"),
        ("Sharpe ratio", num(mt["sharpe"]), "Return per unit of volatility, 0% risk-free rate"),
        ("Sortino ratio", num(mt["sortino"]), "Like Sharpe, counting only downside swings"),
        (
            "Maximum drawdown",
            pct(mt["max_drawdown"]),
            f"Largest fall from a peak (trough {mt['max_drawdown_trough'] or 'n/a'})",
        ),
        ("1-day VaR (95%)", pct(mt["var"], False), "Loss exceeded on about 1 day in 20"),
        ("Expected shortfall", pct(mt["expected_shortfall"], False), "Average loss on those days"),
        ("Beta", num(mt["beta"]), f"Sensitivity to {risk['benchmark_id'] or 'benchmark'}"),
    ]
    pdf.grid(["Metric", "Value", "What it means"], rows, [3, 1.6, 6], "LRL")
    if risk.get("insight"):
        pdf.para(risk["insight"])
    if risk.get("warning"):
        pdf.para(risk["warning"], muted=True)

    f = forecast_service.latest(session, inst)
    pdf.h2("Forecast check")
    if not f["available"]:
        pdf.para(f.get("reason") or "No forecast is available for this asset.", muted=True)
    else:
        for h in f["horizons"]:
            rng = f"{money(h['lower'], ccy, digits)} to {money(h['upper'], ccy, digits)}"
            if h["beats_baseline"]:
                text = (
                    f"{h['horizon_days']} trading days from {h['as_of']}: "
                    f"{h['best_model_label']} points to {money(h['point'], ccy, digits)}, "
                    f"80% range {rng}. Its past errors were {pct(h['skill'], False, 0)} "
                    "smaller than assuming no change."
                )
            else:
                text = (
                    f"{h['horizon_days']} trading days from {h['as_of']}: no model beat the "
                    f"no-change baseline, so there is no forecast. Past moves of this length "
                    f"ended between {rng} 80% of the time."
                )
            pdf.para(text)

    flags = alert_service.list_anomalies(session, inst.id, 180, 8)
    pdf.h2("Unusual activity, past 6 months")
    if flags:
        pdf.grid(
            ["Date", "Flag", "Detail"],
            [(a["observed_at"], a["label"], a["description"]) for a in flags],
            [1.6, 2.2, 7],
            "LLL",
        )
        pdf.para(
            "Statistical flags from a robust z-score against the prior year; they are not "
            "verified news events.",
            8.5,
            muted=True,
        )
    else:
        pdf.para("No statistical flags in the past six months.", muted=True)

    sources = [PRICE_SOURCE]
    news = news_service.instrument_news(session, inst, 6)
    if news["articles"]:
        pdf.h2("Recent headlines")
        pdf.grid(
            ["Date", "Source", "Headline", "Tone"],
            [
                (
                    a["published_at"].date().isoformat(),
                    a["source"],
                    a["headline"],
                    a["sentiment"]["label"] if a["sentiment"] else "",
                )
                for a in news["articles"]
            ],
            [1.6, 1.8, 7.6, 1.3],
            "LLLL",
        )
        pdf.para(
            "Tone is FinBERT's reading of the headline only and says nothing about price.",
            8.5,
            muted=True,
        )
        sources.append("Finnhub headlines; tone from FinBERT (ProsusAI/finbert)")

    fund = fundamentals_service.fundamentals(session, inst)
    if fund.get("available", True) and fund.get("years"):
        fccy = fund["currency"]
        pdf.h2(f"Financials from SEC filings ({fccy} millions)")
        years = fund["years"][-4:]

        def mn(v: float | None) -> str:
            return "n/a" if v is None else f"{v / 1e6:,.0f}"

        pdf.grid(
            ["Fiscal year", "Revenue", "Growth", "Net income", "Net margin", "Free cash flow"],
            [
                (
                    y["fiscal_year"],
                    mn(y.get("revenue")),
                    pct(y.get("revenue_growth")),
                    mn(y.get("net_income")),
                    pct(y.get("net_margin"), False),
                    mn(y.get("free_cash_flow")),
                )
                for y in years
            ],
            [1.4, 1.6, 1.2, 1.6, 1.3, 1.8],
        )
        sources.append(fund["source"])

    pdf.disclaimer(
        [*risk["assumptions"], "Forecasts: docs/MODELS.md in the MarketPulse repository."],
        sources,
    )
    return pdf.output_bytes()


def asset_prices_csv(session: Session, instrument_id: str, period: str) -> str:
    inst = md.get_instrument(session, instrument_id)
    hist = svc.history(session, inst, period, None)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["date", "open", "high", "low", "close", "volume", "currency", "quality"])
    for b in hist["bars"]:
        w.writerow(
            [
                b["date"],
                b["open"],
                b["high"],
                b["low"],
                b["close"],
                b["volume"],
                hist["currency"],
                b["quality"],
            ]
        )
    return buf.getvalue()


# --- portfolio report -----------------------------------------------------------


def portfolio_pdf(session: Session, p: Portfolio) -> bytes:
    s = ps.summary(session, p)
    if not s["holdings"]:
        raise AppError("empty_portfolio", "Add holdings before creating a report", 422)
    base = p.base_currency
    t = s["totals"]

    pdf = Report(f"{p.name} portfolio report")
    pdf.alias_nb_pages()
    pdf.title_block(
        p.name,
        f"Portfolio report in {base}. Valued at closes up to {s['as_of'] or 'n/a'}. "
        "Private: generated for the signed-in owner only.",
    )

    pdf.h2("Summary")
    pdf.grid(
        ["Measure", "Value"],
        [
            ("Market value", money(t["value"], base)),
            ("Cost basis", money(t["cost"], base)),
            (
                "Unrealised gain or loss",
                f"{money(t['unrealized'], base)} ({pct(t['unrealized_pct'])})",
            ),
            ("  from price moves", money(t["price_effect"], base)),
            ("  from currency moves", money(t["fx_effect"], base)),
            ("Realised gain or loss", money(t["realized"], base)),
            ("Fees paid", money(t["fees"], base)),
        ],
        [3, 2],
    )

    pdf.h2("Holdings")
    pdf.grid(
        ["Holding", "Quantity", "Avg cost", "Last price", f"Value ({base})", "Weight", "Gain"],
        [
            (
                h["name"],
                f"{h['quantity']:,.4g} {'' if h['unit'] == 'unit' else h['unit']}".strip(),
                num(h["average_cost"], price_digits(h["average_cost"])),
                num(h["price"], price_digits(h["price"])),
                num(h["value_base"]),
                pct(h["weight"], False),
                pct(h["unrealized_pct"]),
            )
            for h in s["holdings"]
        ],
        [3.4, 1.5, 1.4, 1.4, 1.7, 1.1, 1.1],
    )
    pdf.para(
        f"Average cost and last price are in each holding's own currency; value is in {base}.",
        8.5,
        muted=True,
    )

    alloc = s["allocation"].get("asset_class") or []
    if alloc:
        pdf.h2("Allocation by asset class")
        pdf.grid(
            ["Asset class", "Weight", f"Value ({base})"],
            [(a["label"], pct(a["weight"], False), num(a.get("value"))) for a in alloc],
            [3, 1.5, 2],
        )

    methodology = list(s["notes"])
    try:
        perf = ps.performance(session, p, "1Y")
    except AppError:
        perf = None
    if perf:
        mt = perf["metrics"]
        bench = perf["benchmark"]
        pdf.h2("Performance and risk, past year")
        if perf.get("insight"):
            pdf.para(perf["insight"])
        series = [("Portfolio", _chart_points(perf["portfolio"], "value"), ACCENT)]
        if bench["points"]:
            series.append(
                (bench["name"] or "Benchmark", _chart_points(bench["points"], "value"), MUTED)
            )
        pdf.line_chart(series, (perf["start"], perf["end"]), fmt=lambda v: f"{v:.0f}")
        pdf.para("Growth of 100 at the start of the period.", 8.5, muted=True)
        pdf.grid(
            ["Metric", "Value"],
            [
                ("Time-weighted return", pct(mt["time_weighted_return"])),
                (f"Benchmark ({bench['name'] or 'none'})", pct(mt["benchmark_return"])),
                ("Annualised volatility", pct(mt["volatility"], False)),
                ("Sharpe ratio", num(mt["sharpe"])),
                ("Maximum drawdown", pct(mt["max_drawdown"])),
                ("1-day VaR (95%)", pct(mt["var"], False)),
            ],
            [3, 2],
        )
        if perf.get("warning"):
            pdf.para(perf["warning"], muted=True)
        risk_rows = [r for r in perf["risk"] if r.get("risk_contribution") is not None]
        if risk_rows:
            pdf.h2("Where the risk comes from")
            pdf.grid(
                ["Holding", "Weight", "Volatility", "Share of risk"],
                [
                    (
                        r["name"],
                        pct(r["weight"], False),
                        pct(r["volatility"], False),
                        pct(r["risk_contribution"], False),
                    )
                    for r in sorted(risk_rows, key=lambda r: -(r["risk_contribution"] or 0))
                ],
                [4, 1.5, 1.5, 1.5],
            )
        methodology += perf["assumptions"]

    pdf.h2("Stress scenarios")
    rows = []
    for key, preset in svc.STRESS_PRESETS.items():
        try:
            r = ps.stress(session, p, key, None)
        except AppError:
            continue
        rows.append((preset["label"], preset["description"], pct(r["total"]), num(r["pnl"])))
    if rows:
        pdf.grid(
            ["Scenario", "Shocks", "Change", f"Gain or loss ({base})"],
            rows,
            [2.6, 5.2, 1.1, 1.9],
            "LLRR",
        )
        pdf.para("Hypothetical shocks applied to today's holdings, not forecasts.", 8.5, muted=True)

    pdf.disclaimer(
        methodology,
        [PRICE_SOURCE, "Your recorded transactions in MarketPulse"],
    )
    return pdf.output_bytes()


def portfolio_holdings_csv(session: Session, p: Portfolio) -> str:
    s = ps.summary(session, p)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "instrument_id",
            "name",
            "asset_class",
            "currency",
            "unit",
            "quantity",
            "average_cost",
            "last_price",
            f"cost_{p.base_currency.lower()}",
            f"value_{p.base_currency.lower()}",
            "weight",
            f"unrealized_{p.base_currency.lower()}",
            "unrealized_pct",
            "as_of",
        ]
    )
    for h in s["holdings"]:
        w.writerow(
            [
                h["instrument_id"],
                h["name"],
                h["asset_class"],
                h["currency"],
                h["unit"],
                h["quantity"],
                h["average_cost"],
                h["price"],
                h["cost_base"],
                h["value_base"],
                h["weight"],
                h["unrealized_base"],
                h["unrealized_pct"],
                s["as_of"],
            ]
        )
    return buf.getvalue()
