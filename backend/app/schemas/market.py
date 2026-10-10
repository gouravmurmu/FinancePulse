"""Response models for market endpoints."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Freshness(BaseModel):
    kind: Literal["live", "delayed", "eod", "stale", "unavailable", "demo"]
    as_of: date | None = None


class InstrumentOut(BaseModel):
    id: str
    name: str
    asset_class: str
    exchange: str | None
    country: str | None
    currency: str
    timezone: str
    price_definition: str | None
    region: str
    sector: str | None = None
    benchmark_id: str | None = None


class Quote(BaseModel):
    instrument_id: str
    name: str
    asset_class: str
    region: str
    price: float | None
    change: float | None
    change_pct: float | None
    currency: str
    converted: bool
    as_of: date | None
    freshness: Freshness
    sparkline: list[float]
    sector: str | None = None


class Point(BaseModel):
    date: date
    value: float


class SeriesOut(BaseModel):
    instrument_id: str
    points: list[Point]


class Comparison(BaseModel):
    period: str
    start: date | None
    series: list[SeriesOut]
    notes: list[str]


class MarketSession(BaseModel):
    session: str
    name: str
    timezone: str
    open: bool


class DataStatus(BaseModel):
    status: str
    started_at: datetime
    finished_at: datetime | None
    last_success_at: datetime | None
    failed: list[str]


class Overview(BaseModel):
    region: str
    currency: str
    period: str
    indices: list[Quote]
    snapshots: list[Quote]
    gainers: list[Quote]
    losers: list[Quote]
    heatmap: list[Quote]
    comparison: Comparison
    markets: list[MarketSession]
    data_status: DataStatus | None
    refresh_schedule: str = Field(
        default="Daily bars refreshed at 11:00 and 22:30 UTC. Prices are delayed or end of day."
    )


class Bar(BaseModel):
    date: date
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: float | None
    quote_type: str
    quality: str


class History(BaseModel):
    instrument_id: str
    currency: str
    converted: bool
    provider: str | None = None
    retrieved_at: datetime | None = None
    bars: list[Bar]
    source_note: str = "Yahoo Finance via yfinance (unofficial; delayed or end of day)."


class Snapshot(BaseModel):
    provider: str
    as_of: datetime
    market_cap: float | None
    circulating_supply: float | None
    total_supply: float | None
    max_supply: float | None
    volume_24h: float | None
    source_note: str = "CoinGecko"


class InstrumentDetail(BaseModel):
    instrument: InstrumentOut
    quote: Quote
    market_open: bool | None
    snapshot: Snapshot | None
    related: list[InstrumentOut]
    metal_context: dict[str, Any] | None = None


class Indicators(BaseModel):
    instrument_id: str
    currency: str | None = None
    series: dict[str, list[Point]]


class RiskMetrics(BaseModel):
    total_return: float | None
    cagr: float | None
    volatility: float | None
    sharpe: float | None
    sortino: float | None
    max_drawdown: float | None
    max_drawdown_peak: date | None
    max_drawdown_trough: date | None
    max_drawdown_recovery: date | None
    var: float | None
    expected_shortfall: float | None
    beta: float | None


class InstrumentRisk(BaseModel):
    instrument_id: str
    period: str
    observations: int
    periods_per_year: int
    confidence: float
    benchmark_id: str | None
    metrics: RiskMetrics
    risk_level: Literal["low", "moderate", "high"] | None
    drawdown: list[Point]
    rolling_volatility: list[Point]
    assumptions: list[str]
    insight: str | None
    warning: str | None = None


class RiskLabRequest(BaseModel):
    instrument_ids: list[str] = Field(min_length=2, max_length=8)
    period: str = "1Y"
    confidence: float = Field(0.95, gt=0.5, lt=1)
    window: int = Field(60, ge=10, le=252)


class MonteCarloRequest(BaseModel):
    weights: dict[str, float] = Field(min_length=1, max_length=8)
    initial_value: float = Field(10000, gt=0, le=1e12)
    horizon_days: int = Field(252, ge=1, le=2520)
    paths: int = Field(2000, ge=100, le=10000)
    seed: int = Field(42, ge=0, le=2**31)
    lookback: str = "3Y"


class StressRequest(BaseModel):
    weights: dict[str, float] = Field(min_length=1, max_length=20)
    shocks: dict[str, float] | None = None
    preset: str | None = None


class FundamentalYear(BaseModel):
    fiscal_year: int
    period_end: date
    revenue: float | None
    gross_profit: float | None
    operating_income: float | None
    net_income: float | None
    eps_diluted: float | None
    operating_cash_flow: float | None
    capex: float | None
    total_assets: float | None
    total_liabilities: float | None
    equity: float | None
    long_term_debt: float | None
    cash: float | None
    gross_margin: float | None
    operating_margin: float | None
    net_margin: float | None
    free_cash_flow: float | None
    debt_to_equity: float | None
    revenue_growth: float | None
    net_income_growth: float | None


class Fundamentals(BaseModel):
    instrument_id: str
    available: bool
    reason: str | None
    currency: str
    source: str
    years: list[FundamentalYear]
    last_filed: date | None
    retrieved_at: datetime | None
