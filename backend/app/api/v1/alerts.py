import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Query, Response

from app.api.deps import DbSession, UserId
from app.schemas.alerts import AlertRuleCreate, AlertRuleUpdate, MarkRead
from app.services import alert_service as alerts
from app.services import market_data as md

router = APIRouter(tags=["alerts"])


@router.get("/anomalies", summary="Recent statistical anomalies (public)")
def list_anomalies(
    session: DbSession,
    instrument_id: str | None = None,
    days: Annotated[int, Query(ge=1, le=1825)] = 30,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[dict[str, Any]]:
    if instrument_id:
        md.get_instrument(session, instrument_id)
    return alerts.list_anomalies(session, instrument_id, days, limit)


@router.get("/alerts/rules", summary="Your alert rules")
def list_rules(user: UserId, session: DbSession) -> list[dict[str, Any]]:
    return alerts.list_rules(session, user)


@router.post("/alerts/rules", status_code=201)
def create_rule(user: UserId, session: DbSession, body: AlertRuleCreate) -> dict[str, Any]:
    return alerts.create_rule(session, user, body.instrument_id, body.kind, body.threshold)


@router.patch("/alerts/rules/{rule_id}")
def update_rule(
    user: UserId, session: DbSession, rule_id: uuid.UUID, body: AlertRuleUpdate
) -> dict[str, Any]:
    return alerts.update_rule(session, user, rule_id, body.threshold, body.active)


@router.delete("/alerts/rules/{rule_id}", status_code=204)
def delete_rule(user: UserId, session: DbSession, rule_id: uuid.UUID) -> Response:
    alerts.delete_rule(session, user, rule_id)
    return Response(status_code=204)


@router.get("/alerts/events", summary="Alerts that have fired for you")
def list_events(user: UserId, session: DbSession, unread_only: bool = False) -> dict[str, Any]:
    return alerts.list_events(session, user, unread_only)


@router.post("/alerts/events/read")
def mark_read(user: UserId, session: DbSession, body: MarkRead) -> dict[str, int]:
    return {"updated": alerts.mark_read(session, user, body.ids)}
