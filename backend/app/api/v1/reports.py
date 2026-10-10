"""Downloadable reports. Asset reports are public; portfolio reports are owner-only."""

import re
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Response

from app.api.deps import DbSession, UserId
from app.api.v1.instruments import PeriodQ
from app.services import portfolio_service as ps
from app.services import report_service as rs

router = APIRouter(prefix="/reports", tags=["reports"])


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "report"


def _file(body: bytes | str, media: str, name: str, private: bool) -> Response:
    stamp = datetime.now(UTC).strftime("%Y-%m-%d")
    return Response(
        body,
        media_type=media,
        headers={
            "content-disposition": f'attachment; filename="{name}-{stamp}.{media.split("/")[1]}"',
            "cache-control": "private, no-store" if private else "public, max-age=900",
        },
    )


@router.get("/asset/{instrument_id}/pdf", summary="One-asset PDF report")
def asset_pdf(session: DbSession, instrument_id: str) -> Response:
    return _file(
        rs.asset_pdf(session, instrument_id), "application/pdf", _slug(instrument_id), False
    )


@router.get("/asset/{instrument_id}/csv", summary="Daily prices as CSV")
def asset_csv(session: DbSession, instrument_id: str, period: PeriodQ = "5Y") -> Response:
    body = rs.asset_prices_csv(session, instrument_id, period)
    return _file(body, "text/csv", f"{_slug(instrument_id)}-prices", False)


@router.get("/portfolio/{portfolio_id}/pdf", summary="Portfolio PDF report")
def portfolio_pdf(user: UserId, session: DbSession, portfolio_id: uuid.UUID) -> Response:
    p = ps.get_portfolio(session, user, portfolio_id)
    return _file(rs.portfolio_pdf(session, p), "application/pdf", _slug(p.name), True)


@router.get("/portfolio/{portfolio_id}/csv", summary="Current holdings as CSV")
def portfolio_csv(user: UserId, session: DbSession, portfolio_id: uuid.UUID) -> Response:
    p = ps.get_portfolio(session, user, portfolio_id)
    return _file(
        rs.portfolio_holdings_csv(session, p), "text/csv", f"{_slug(p.name)}-holdings", True
    )
