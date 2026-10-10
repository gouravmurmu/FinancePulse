"""Writes used by batch jobs: universe sync and idempotent upserts."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, time
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.data.universe import InstrumentDef
from app.models import (
    Fundamental,
    Instrument,
    InstrumentAlias,
    InstrumentSnapshot,
    JobRun,
    MarketObservation,
)
from app.providers.base import Observation, Snapshot
from app.providers.sec import FundamentalFact

BATCH = 1000


def sync_universe(session: Session, universe: Iterable[InstrumentDef]) -> int:
    """Upsert instruments and replace their aliases. Never deletes instruments
    (IDs are stable); ones dropped from the universe are marked inactive."""
    defs = list(universe)
    ids = [d.id for d in defs]
    for d in defs:
        attributes: dict[str, Any] = {**d.attributes, "region": d.region}
        stmt = insert(Instrument).values(
            id=d.id,
            name=d.name,
            asset_class=d.asset_class,
            exchange=d.exchange,
            country=d.country,
            currency=d.currency,
            timezone=d.timezone,
            price_definition=d.price_definition,
            is_active=True,
            attributes=attributes,
        )
        session.execute(
            stmt.on_conflict_do_update(
                index_elements=[Instrument.id],
                set_={
                    "name": stmt.excluded.name,
                    "asset_class": stmt.excluded.asset_class,
                    "exchange": stmt.excluded.exchange,
                    "country": stmt.excluded.country,
                    "currency": stmt.excluded.currency,
                    "timezone": stmt.excluded.timezone,
                    "price_definition": stmt.excluded.price_definition,
                    "is_active": True,
                    "attributes": stmt.excluded.attributes,
                    "updated_at": func.now(),
                },
            )
        )
    session.execute(delete(InstrumentAlias).where(InstrumentAlias.instrument_id.in_(ids)))
    alias_rows = []
    for d in defs:
        for provider, symbol in d.aliases.items():
            alias_rows.append({"instrument_id": d.id, "provider": provider, "alias": symbol})
        for term in {d.id, d.name, *d.search}:
            alias_rows.append({"instrument_id": d.id, "provider": "search", "alias": term})
    if alias_rows:
        session.execute(insert(InstrumentAlias).values(alias_rows).on_conflict_do_nothing())
    session.query(Instrument).filter(Instrument.id.notin_(ids)).update(
        {"is_active": False}, synchronize_session=False
    )
    return len(defs)


def upsert_observations(session: Session, observations: list[Observation]) -> int:
    rows = [
        {
            "instrument_id": o.instrument_id,
            "provider": o.provider,
            "frequency": "1d",
            # Daily bars are keyed by trading date, stored as 00:00 UTC of that date.
            "observed_at": datetime.combine(o.trading_date, time.min, tzinfo=UTC),
            "retrieved_at": o.retrieved_at,
            "currency": o.currency,
            "open": o.open,
            "high": o.high,
            "low": o.low,
            "close": o.close,
            "adj_close": o.adj_close,
            "volume": o.volume,
            "quote_type": o.quote_type,
            "quality_status": o.quality_status,
            "provenance": o.provenance,
        }
        for o in observations
    ]
    for i in range(0, len(rows), BATCH):
        stmt = insert(MarketObservation).values(rows[i : i + BATCH])
        session.execute(
            stmt.on_conflict_do_update(
                constraint="uq_market_observations_key",
                set_={
                    c: stmt.excluded[c]
                    for c in (
                        "retrieved_at",
                        "currency",
                        "open",
                        "high",
                        "low",
                        "close",
                        "adj_close",
                        "volume",
                        "quote_type",
                        "quality_status",
                        "provenance",
                    )
                },
            )
        )
    return len(rows)


def upsert_snapshots(session: Session, snapshots: list[Snapshot]) -> int:
    for s in snapshots:
        values = {
            "instrument_id": s.instrument_id,
            "provider": s.provider,
            "as_of": s.as_of,
            "retrieved_at": s.retrieved_at,
            "price": s.price,
            "market_cap": s.market_cap,
            "circulating_supply": s.circulating_supply,
            "total_supply": s.total_supply,
            "max_supply": s.max_supply,
            "volume_24h": s.volume_24h,
        }
        stmt = insert(InstrumentSnapshot).values(values)
        session.execute(
            stmt.on_conflict_do_update(
                index_elements=[InstrumentSnapshot.instrument_id],
                set_={k: v for k, v in values.items() if k != "instrument_id"},
            )
        )
    return len(snapshots)


def upsert_fundamentals(session: Session, facts: list[FundamentalFact]) -> int:
    for f in facts:
        values = {
            "instrument_id": f.instrument_id,
            "concept": f.concept,
            "fiscal_year": f.fiscal_year,
            "period_start": f.period_start,
            "period_end": f.period_end,
            "value": f.value,
            "unit": f.unit,
            "source_tag": f.source_tag,
            "form": f.form,
            "filed": f.filed,
            "accession": f.accession,
            "retrieved_at": f.retrieved_at,
        }
        stmt = insert(Fundamental).values(values)
        session.execute(
            stmt.on_conflict_do_update(
                constraint="uq_fundamentals_key",
                set_={
                    k: v
                    for k, v in values.items()
                    if k not in ("instrument_id", "concept", "period_end")
                },
            )
        )
    return len(facts)


def latest_trading_date(session: Session, instrument_id: str) -> datetime | None:
    return session.execute(
        select(func.max(MarketObservation.observed_at)).where(
            MarketObservation.instrument_id == instrument_id
        )
    ).scalar_one_or_none()


def start_job(session: Session, job: str) -> JobRun:
    run = JobRun(job=job, started_at=datetime.now(UTC), status="running", details={})
    session.add(run)
    session.commit()
    return run


def finish_job(session: Session, run: JobRun, status: str, details: dict[str, Any]) -> None:
    run.status = status
    run.finished_at = datetime.now(UTC)
    run.details = details
    session.commit()
