"""Read side of market data: instruments, price frames, freshness, currency."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

import pandas as pd
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.data.universe import USDINR_ID
from app.models import Instrument, InstrumentAlias, InstrumentSnapshot, JobRun, MarketObservation
from app.services.cache import ttl_cache

Period = Literal["1D", "1W", "1M", "3M", "6M", "YTD", "1Y", "3Y", "5Y", "MAX"]
PERIODS: tuple[str, ...] = ("1D", "1W", "1M", "3M", "6M", "YTD", "1Y", "3Y", "5Y", "MAX")
DisplayCurrency = Literal["USD", "INR"]
CACHE_S = 300

# How old the latest bar may be before it is shown as stale.
STALE_AFTER_DAYS = {"crypto": 2, "default": 4}


def period_start(period: str, today: date) -> date | None:
    """First calendar date included in a period. 1D is handled by callers as
    "last bar vs previous bar"; it starts a month back so sparklines show the
    recent trend."""
    days = {"1D": 31, "1W": 7, "1M": 30, "3M": 91, "6M": 182, "1Y": 365, "3Y": 1096, "5Y": 1826}
    if period == "YTD":
        return date(today.year, 1, 1)
    if period == "MAX":
        return None
    if period not in days:
        raise AppError("invalid_period", f"Unknown period {period!r}", 422)
    return today - timedelta(days=days[period])


@dataclass(frozen=True)
class InstrumentInfo:
    id: str
    name: str
    asset_class: str
    exchange: str | None
    country: str | None
    currency: str
    timezone: str
    price_definition: str | None
    region: str
    attributes: dict[str, Any]


def _info(row: Instrument) -> InstrumentInfo:
    attrs = dict(row.attributes or {})
    return InstrumentInfo(
        id=row.id,
        name=row.name,
        asset_class=row.asset_class,
        exchange=row.exchange,
        country=row.country,
        currency=row.currency,
        timezone=row.timezone,
        price_definition=row.price_definition,
        region=attrs.pop("region", "global"),
        attributes=attrs,
    )


@ttl_cache(CACHE_S)
def list_instruments(session: Session) -> list[InstrumentInfo]:
    rows = session.scalars(
        select(Instrument).where(Instrument.is_active).order_by(Instrument.name)
    ).all()
    return [_info(r) for r in rows]


def get_instrument(session: Session, instrument_id: str) -> InstrumentInfo:
    for inst in list_instruments(session):
        if inst.id == instrument_id:
            return inst
    raise AppError("instrument_not_found", f"No instrument with id {instrument_id!r}", 404)


def search_instruments(session: Session, q: str, limit: int = 10) -> list[InstrumentInfo]:
    """Ranked: exact alias match, then prefix, then substring (case-insensitive)."""
    term = q.strip().lower()
    if not term:
        return []
    alias = func.lower(InstrumentAlias.alias)
    rows = session.execute(
        select(InstrumentAlias.instrument_id, alias)
        .join(Instrument, Instrument.id == InstrumentAlias.instrument_id)
        .where(Instrument.is_active)
        .where(or_(alias.contains(term), func.lower(Instrument.name).contains(term)))
    ).all()
    score: dict[str, int] = {}
    for inst_id, a in rows:
        s = 3 if a == term else 2 if a.startswith(term) else 1
        score[inst_id] = max(score.get(inst_id, 0), s)
    by_id = {i.id: i for i in list_instruments(session)}
    for inst in by_id.values():
        if term in inst.name.lower():
            score[inst.id] = max(
                score.get(inst.id, 0), 2 if inst.name.lower().startswith(term) else 1
            )
    ranked = sorted(score, key=lambda i: (-score[i], by_id[i].name if i in by_id else i))
    return [by_id[i] for i in ranked if i in by_id][:limit]


def load_bars(session: Session, instrument_id: str, start: date | None) -> pd.DataFrame:
    """Daily bars indexed by trading date. Excludes rows flagged as rejected.
    Returns a copy, so callers may modify it without touching the cache."""
    return _load_bars(session, instrument_id, start).copy()


@ttl_cache(CACHE_S)
def _load_bars(session: Session, instrument_id: str, start: date | None) -> pd.DataFrame:
    stmt = (
        select(
            MarketObservation.observed_at,
            MarketObservation.open,
            MarketObservation.high,
            MarketObservation.low,
            MarketObservation.close,
            MarketObservation.adj_close,
            MarketObservation.volume,
            MarketObservation.quote_type,
            MarketObservation.quality_status,
            MarketObservation.retrieved_at,
            MarketObservation.provider,
        )
        .where(MarketObservation.instrument_id == instrument_id)
        .where(MarketObservation.frequency == "1d")
        .where(MarketObservation.quality_status != "rejected")
        .order_by(MarketObservation.observed_at)
    )
    if start is not None:
        stmt = stmt.where(
            MarketObservation.observed_at >= datetime.combine(start, datetime.min.time(), UTC)
        )
    rows = session.execute(stmt).all()
    if not rows:
        return pd.DataFrame(
            columns=[
                "open",
                "high",
                "low",
                "close",
                "adj_close",
                "volume",
                "quote_type",
                "quality_status",
                "retrieved_at",
                "provider",
            ]
        )
    df = pd.DataFrame(
        rows,
        columns=[
            "date",
            "open",
            "high",
            "low",
            "close",
            "adj_close",
            "volume",
            "quote_type",
            "quality_status",
            "retrieved_at",
            "provider",
        ],
    )
    df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_localize(None).dt.normalize()
    for col in ("open", "high", "low", "close", "adj_close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
    return df.set_index("date")


def total_return_series(bars: pd.DataFrame) -> pd.Series:
    """Adjusted close (splits + dividends) where available, else close."""
    if bars.empty:
        return pd.Series(dtype=float)
    adj = bars["adj_close"]
    return adj.where(adj.notna(), bars["close"]).astype(float)


def closes_frame(
    session: Session, ids: list[str], start: date | None, adjusted: bool = True
) -> pd.DataFrame:
    cols = {}
    for i in ids:
        bars = load_bars(session, i, start)
        cols[i] = total_return_series(bars) if adjusted else bars["close"]
    return pd.DataFrame(cols).sort_index()


def fx_series(session: Session, start: date | None) -> pd.Series:
    bars = load_bars(session, USDINR_ID, start)
    return bars["close"] if not bars.empty else pd.Series(dtype=float)


def convert(
    series: pd.Series, from_ccy: str, to_ccy: str, usdinr: pd.Series
) -> tuple[pd.Series, bool]:
    """Convert a USD or INR price series into the display currency using the
    USD/INR close of the same date (last known rate carried forward)."""
    if from_ccy == to_ccy or from_ccy not in ("USD", "INR") or series.empty:
        return series, False
    if usdinr.empty:
        raise AppError("fx_unavailable", "USD/INR rates are not available yet", 503)
    rate = usdinr.reindex(series.index.union(usdinr.index)).sort_index().ffill()
    rate = rate.reindex(series.index)
    if rate.isna().all():
        raise AppError("fx_unavailable", "No USD/INR rate covers this period", 503)
    converted = series * rate if from_ccy == "USD" else series / rate
    return converted.dropna(), True


def freshness(
    asset_class: str, last_date: date | None, quote_type: str | None, today: date
) -> dict[str, Any]:
    if last_date is None:
        return {"kind": "unavailable"}
    limit = STALE_AFTER_DAYS["crypto" if asset_class == "crypto" else "default"]
    if (today - last_date).days > limit:
        return {"kind": "stale", "as_of": last_date.isoformat()}
    if quote_type == "delayed":
        return {"kind": "delayed", "as_of": last_date.isoformat()}
    return {"kind": "eod", "as_of": last_date.isoformat()}


def get_snapshot(session: Session, instrument_id: str) -> InstrumentSnapshot | None:
    return session.get(InstrumentSnapshot, instrument_id)


@ttl_cache(60)
def last_job_run(session: Session, job: str) -> dict[str, Any] | None:
    run = session.scalars(
        select(JobRun).where(JobRun.job == job).order_by(JobRun.started_at.desc()).limit(1)
    ).first()
    if run is None:
        return None
    last_ok = session.scalars(
        select(JobRun.finished_at)
        .where(JobRun.job == job, JobRun.status.in_(("success", "partial")))
        .order_by(JobRun.started_at.desc())
        .limit(1)
    ).first()
    return {
        "status": run.status,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "last_success_at": last_ok,
        "failed": (run.details or {}).get("failed", []),
    }
