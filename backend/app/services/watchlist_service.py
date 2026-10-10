"""Watchlists: named lists of instruments with quotes. Filtered by user id."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Watchlist, WatchlistItem
from app.services import analytics_service as svc
from app.services import market_data as md

MAX_WATCHLISTS = 20
MAX_ITEMS = 50


def _get(session: Session, user_id: uuid.UUID, watchlist_id: uuid.UUID) -> Watchlist:
    w = session.scalar(
        select(Watchlist).where(Watchlist.id == watchlist_id, Watchlist.user_id == user_id)
    )
    if w is None:
        raise AppError("not_found", "Watchlist not found", 404)
    return w


def _items(session: Session, w: Watchlist) -> list[WatchlistItem]:
    return list(
        session.scalars(
            select(WatchlistItem)
            .where(WatchlistItem.watchlist_id == w.id, WatchlistItem.user_id == w.user_id)
            .order_by(WatchlistItem.position, WatchlistItem.created_at)
        )
    )


def watchlist_out(
    session: Session,
    w: Watchlist,
    with_quotes: bool,
    period: str = "1D",
    currency: str | None = None,
) -> dict[str, Any]:
    items = _items(session, w)
    out: dict[str, Any] = {
        "id": w.id,
        "name": w.name,
        "instrument_ids": [i.instrument_id for i in items],
    }
    if with_quotes:
        out["quotes"] = [
            svc.quote(session, md.get_instrument(session, i.instrument_id), period, currency)
            for i in items
        ]
    return out


def list_watchlists(session: Session, user_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(Watchlist).where(Watchlist.user_id == user_id).order_by(Watchlist.created_at)
    ).all()
    return [watchlist_out(session, w, False) for w in rows]


def get_watchlist(
    session: Session, user_id: uuid.UUID, watchlist_id: uuid.UUID, period: str, currency: str | None
) -> dict[str, Any]:
    return watchlist_out(session, _get(session, user_id, watchlist_id), True, period, currency)


def create_watchlist(session: Session, user_id: uuid.UUID, name: str) -> dict[str, Any]:
    count = session.scalar(
        select(func.count()).select_from(Watchlist).where(Watchlist.user_id == user_id)
    )
    if (count or 0) >= MAX_WATCHLISTS:
        raise AppError("limit_reached", f"You can have up to {MAX_WATCHLISTS} watchlists", 422)
    w = Watchlist(user_id=user_id, name=name.strip())
    session.add(w)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise AppError("conflict", "You already have a watchlist with this name", 409) from exc
    session.commit()
    return watchlist_out(session, w, False)


def rename_watchlist(
    session: Session, user_id: uuid.UUID, watchlist_id: uuid.UUID, name: str
) -> dict[str, Any]:
    w = _get(session, user_id, watchlist_id)
    w.name = name.strip()
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise AppError("conflict", "You already have a watchlist with this name", 409) from exc
    return watchlist_out(session, w, False)


def delete_watchlist(session: Session, user_id: uuid.UUID, watchlist_id: uuid.UUID) -> None:
    session.delete(_get(session, user_id, watchlist_id))
    session.commit()


def add_item(
    session: Session, user_id: uuid.UUID, watchlist_id: uuid.UUID, instrument_id: str
) -> dict[str, Any]:
    w = _get(session, user_id, watchlist_id)
    md.get_instrument(session, instrument_id)
    items = _items(session, w)
    if any(i.instrument_id == instrument_id for i in items):
        return watchlist_out(session, w, False)
    if len(items) >= MAX_ITEMS:
        raise AppError("limit_reached", f"A watchlist can hold up to {MAX_ITEMS} instruments", 422)
    session.add(
        WatchlistItem(
            watchlist_id=w.id, user_id=user_id, instrument_id=instrument_id, position=len(items)
        )
    )
    session.commit()
    return watchlist_out(session, w, False)


def remove_item(
    session: Session, user_id: uuid.UUID, watchlist_id: uuid.UUID, instrument_id: str
) -> None:
    w = _get(session, user_id, watchlist_id)
    for i in _items(session, w):
        if i.instrument_id == instrument_id:
            session.delete(i)
    session.commit()
