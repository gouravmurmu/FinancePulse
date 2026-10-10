import uuid
from typing import Any, Literal

from fastapi import APIRouter, Response

from app.api.deps import DbSession, UserId
from app.api.v1.instruments import PeriodQ
from app.schemas.portfolio import WatchlistCreate, WatchlistItemIn
from app.services import watchlist_service as ws

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


@router.get("", summary="Your watchlists")
def list_watchlists(user: UserId, session: DbSession) -> list[dict[str, Any]]:
    return ws.list_watchlists(session, user)


@router.post("", status_code=201)
def create_watchlist(user: UserId, session: DbSession, body: WatchlistCreate) -> dict[str, Any]:
    return ws.create_watchlist(session, user, body.name)


@router.get("/{watchlist_id}", summary="A watchlist with quotes")
def get_watchlist(
    user: UserId,
    session: DbSession,
    watchlist_id: uuid.UUID,
    period: PeriodQ = "1D",
    currency: Literal["USD", "INR"] | None = None,
) -> dict[str, Any]:
    return ws.get_watchlist(session, user, watchlist_id, period, currency)


@router.patch("/{watchlist_id}")
def rename_watchlist(
    user: UserId, session: DbSession, watchlist_id: uuid.UUID, body: WatchlistCreate
) -> dict[str, Any]:
    return ws.rename_watchlist(session, user, watchlist_id, body.name)


@router.delete("/{watchlist_id}", status_code=204)
def delete_watchlist(user: UserId, session: DbSession, watchlist_id: uuid.UUID) -> Response:
    ws.delete_watchlist(session, user, watchlist_id)
    return Response(status_code=204)


@router.post("/{watchlist_id}/items", status_code=201)
def add_item(
    user: UserId, session: DbSession, watchlist_id: uuid.UUID, body: WatchlistItemIn
) -> dict[str, Any]:
    return ws.add_item(session, user, watchlist_id, body.instrument_id)


@router.delete("/{watchlist_id}/items/{instrument_id}", status_code=204)
def remove_item(
    user: UserId, session: DbSession, watchlist_id: uuid.UUID, instrument_id: str
) -> Response:
    ws.remove_item(session, user, watchlist_id, instrument_id)
    return Response(status_code=204)
