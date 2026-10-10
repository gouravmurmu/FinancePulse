from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.api.v1.instruments import PeriodQ
from app.core.errors import AppError
from app.core.rate_limit import rate_limit
from app.schemas.market import (
    Comparison,
    MonteCarloRequest,
    Overview,
    RiskLabRequest,
    StressRequest,
)
from app.services import analytics_service as svc
from app.services import market_data as md

router = APIRouter(tags=["markets"])


@router.get("/markets/overview", response_model=Overview, summary="Markets landing data")
def markets_overview(
    session: DbSession,
    region: Literal["global", "india"] = "global",
    currency: Literal["USD", "INR"] = "USD",
    period: PeriodQ = "1D",
) -> Overview:
    return Overview(**svc.overview(session, region, currency, period))


@router.get("/compare", response_model=Comparison, summary="Growth of 100 comparison")
def compare(
    session: DbSession,
    ids: Annotated[str, Query(description="Comma-separated instrument IDs (2-8)")],
    period: PeriodQ = "1Y",
    currency: Literal["USD", "INR"] | None = None,
) -> Comparison:
    id_list = [i for i in ids.split(",") if i]
    if not 1 <= len(id_list) <= 8:
        raise AppError("invalid_selection", "Choose between 1 and 8 instruments", 422)
    return Comparison(**svc.compare(session, id_list, period, currency))


@router.post(
    "/risk/analyze",
    summary="Multi-asset risk comparison",
    dependencies=[rate_limit("risk", 30)],
)
def risk_analyze(session: DbSession, body: RiskLabRequest) -> dict[str, Any]:
    md.period_start(body.period, svc.today_utc())
    return svc.risk_lab(session, body.instrument_ids, body.period, body.confidence, body.window)


@router.post(
    "/risk/monte-carlo",
    summary="Seeded Monte Carlo simulation",
    dependencies=[rate_limit("simulation", 12)],
)
def risk_monte_carlo(session: DbSession, body: MonteCarloRequest) -> dict[str, Any]:
    return svc.run_monte_carlo(
        session,
        body.weights,
        body.initial_value,
        body.horizon_days,
        body.paths,
        body.seed,
        body.lookback,
    )


@router.post("/risk/stress", summary="Instant stress scenario")
def risk_stress(session: DbSession, body: StressRequest) -> dict[str, Any]:
    for i in body.weights:
        md.get_instrument(session, i)
    return svc.run_stress(session, body.weights, body.shocks, body.preset)


@router.get("/risk/stress-presets", summary="Built-in stress scenarios")
def stress_presets() -> list[dict[str, str]]:
    return [
        {"id": k, "label": v["label"], "description": v["description"]}
        for k, v in svc.STRESS_PRESETS.items()
    ]
