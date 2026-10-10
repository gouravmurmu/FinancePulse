from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.schemas.market import (
    Fundamentals,
    History,
    Indicators,
    InstrumentDetail,
    InstrumentOut,
    InstrumentRisk,
    Quote,
    Snapshot,
)
from app.services import analytics_service as svc
from app.services import fundamentals_service
from app.services import market_data as md

router = APIRouter(prefix="/instruments", tags=["instruments"])

PeriodQ = Annotated[str, Query(pattern="^(1D|1W|1M|3M|6M|YTD|1Y|3Y|5Y|MAX)$")]
CurrencyQ = Annotated[Literal["USD", "INR"] | None, Query()]


def to_out(i: md.InstrumentInfo) -> InstrumentOut:
    return InstrumentOut(
        id=i.id,
        name=i.name,
        asset_class=i.asset_class,
        exchange=i.exchange,
        country=i.country,
        currency=i.currency,
        timezone=i.timezone,
        price_definition=i.price_definition,
        region=i.region,
        sector=i.attributes.get("sector"),
        benchmark_id=i.attributes.get("benchmark"),
    )


@router.get("", response_model=list[InstrumentOut], summary="List or search instruments")
def list_instruments(
    session: DbSession,
    q: Annotated[str | None, Query(max_length=50)] = None,
    asset_class: str | None = None,
    region: Literal["global", "india"] | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[InstrumentOut]:
    items = md.search_instruments(session, q, limit=limit) if q else md.list_instruments(session)
    if asset_class:
        items = [i for i in items if i.asset_class == asset_class]
    if region:
        items = [i for i in items if i.region == region]
    return [to_out(i) for i in items[:limit]]


@router.get("/{instrument_id}", response_model=InstrumentDetail)
def instrument_detail(
    session: DbSession, instrument_id: str, period: PeriodQ = "1D", currency: CurrencyQ = None
) -> InstrumentDetail:
    inst = md.get_instrument(session, instrument_id)
    snap = md.get_snapshot(session, inst.id)
    related = [
        i
        for i in md.list_instruments(session)
        if i.id != inst.id
        and i.asset_class == inst.asset_class
        and (i.region == inst.region or inst.asset_class == "crypto")
        and (
            inst.asset_class != "equity"
            or i.attributes.get("sector") == inst.attributes.get("sector")
        )
    ][:6]
    return InstrumentDetail(
        instrument=to_out(inst),
        quote=Quote(**svc.quote(session, inst, period, currency)),
        market_open=svc.instrument_session_open(inst, datetime.now(UTC)),
        snapshot=Snapshot(
            provider=snap.provider,
            as_of=snap.as_of,
            market_cap=svc._f(snap.market_cap),
            circulating_supply=svc._f(snap.circulating_supply),
            total_supply=svc._f(snap.total_supply),
            max_supply=svc._f(snap.max_supply),
            volume_24h=svc._f(snap.volume_24h),
        )
        if snap
        else None,
        related=[to_out(i) for i in related],
        metal_context=svc.metal_context(session, inst, period if period != "1D" else "1Y"),
    )


@router.get("/{instrument_id}/history", response_model=History)
def instrument_history(
    session: DbSession, instrument_id: str, period: PeriodQ = "1Y", currency: CurrencyQ = None
) -> History:
    inst = md.get_instrument(session, instrument_id)
    return History(**svc.history(session, inst, period, currency))


@router.get("/{instrument_id}/indicators", response_model=Indicators)
def instrument_indicators(
    session: DbSession, instrument_id: str, period: PeriodQ = "1Y"
) -> Indicators:
    inst = md.get_instrument(session, instrument_id)
    return Indicators(**svc.indicators(session, inst, period))


@router.get("/{instrument_id}/risk", response_model=InstrumentRisk)
def instrument_risk(
    session: DbSession,
    instrument_id: str,
    period: PeriodQ = "1Y",
    benchmark: str | None = None,
    confidence: Annotated[float, Query(gt=0.5, lt=1)] = 0.95,
) -> InstrumentRisk:
    inst = md.get_instrument(session, instrument_id)
    if benchmark:
        md.get_instrument(session, benchmark)
    return InstrumentRisk(**svc.instrument_risk(session, inst, period, benchmark, confidence))


@router.get("/{instrument_id}/fundamentals", response_model=Fundamentals)
def instrument_fundamentals(session: DbSession, instrument_id: str) -> Fundamentals:
    inst = md.get_instrument(session, instrument_id)
    return Fundamentals(**fundamentals_service.fundamentals(session, inst))
