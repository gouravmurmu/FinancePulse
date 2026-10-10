import uuid
from typing import Any, Literal

from fastapi import APIRouter, Response

from app.api.deps import DbSession, UserId
from app.api.v1.instruments import PeriodQ
from app.core.rate_limit import rate_limit
from app.schemas.portfolio import (
    CsvImport,
    PortfolioCreate,
    PortfolioOut,
    PortfolioStressRequest,
    PortfolioUpdate,
    TransactionIn,
    TransactionOut,
)
from app.services import market_data as md
from app.services import portfolio_service as ps

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


@router.get("", response_model=list[PortfolioOut], summary="Your portfolios")
def list_portfolios(user: UserId, session: DbSession) -> list[dict[str, Any]]:
    return ps.list_portfolios(session, user)


@router.post("", response_model=PortfolioOut, status_code=201, summary="Create a portfolio")
def create_portfolio(user: UserId, session: DbSession, body: PortfolioCreate) -> dict[str, Any]:
    p = ps.create_portfolio(session, user, body.name, body.base_currency, body.benchmark_id)
    return ps.portfolio_out(session, p)


@router.patch("/{portfolio_id}", response_model=PortfolioOut)
def update_portfolio(
    user: UserId, session: DbSession, portfolio_id: uuid.UUID, body: PortfolioUpdate
) -> dict[str, Any]:
    p = ps.get_portfolio(session, user, portfolio_id)
    ps.update_portfolio(session, p, body.model_dump(exclude_unset=True))
    return ps.portfolio_out(session, p)


@router.delete("/{portfolio_id}", status_code=204)
def delete_portfolio(user: UserId, session: DbSession, portfolio_id: uuid.UUID) -> Response:
    ps.delete_portfolio(session, ps.get_portfolio(session, user, portfolio_id))
    return Response(status_code=204)


@router.get("/{portfolio_id}/summary", summary="Holdings, P&L and allocation")
def portfolio_summary(user: UserId, session: DbSession, portfolio_id: uuid.UUID) -> dict[str, Any]:
    return ps.summary(session, ps.get_portfolio(session, user, portfolio_id))


@router.get("/{portfolio_id}/performance", summary="Time-weighted performance and risk")
def portfolio_performance(
    user: UserId, session: DbSession, portfolio_id: uuid.UUID, period: PeriodQ = "1Y"
) -> dict[str, Any]:
    return ps.performance(session, ps.get_portfolio(session, user, portfolio_id), period)


@router.post("/{portfolio_id}/stress", summary="Stress the current holdings")
def portfolio_stress(
    user: UserId, session: DbSession, portfolio_id: uuid.UUID, body: PortfolioStressRequest
) -> dict[str, Any]:
    p = ps.get_portfolio(session, user, portfolio_id)
    for i in body.shocks or {}:
        md.get_instrument(session, i)
    return ps.stress(session, p, body.preset, body.shocks)


@router.get("/{portfolio_id}/transactions", response_model=list[TransactionOut])
def list_transactions(
    user: UserId, session: DbSession, portfolio_id: uuid.UUID
) -> list[dict[str, Any]]:
    return ps.list_transactions(session, ps.get_portfolio(session, user, portfolio_id))


@router.post("/{portfolio_id}/transactions", response_model=TransactionOut, status_code=201)
def add_transaction(
    user: UserId, session: DbSession, portfolio_id: uuid.UUID, body: TransactionIn
) -> dict[str, Any]:
    p = ps.get_portfolio(session, user, portfolio_id)
    (tx,) = ps.add_transactions(session, p, [body.model_dump()])
    names = {tx.instrument_id: ps.display_name(md.get_instrument(session, tx.instrument_id))}
    return ps.transaction_out(tx, names)


@router.put("/{portfolio_id}/transactions/{tx_id}", response_model=TransactionOut)
def update_transaction(
    user: UserId,
    session: DbSession,
    portfolio_id: uuid.UUID,
    tx_id: uuid.UUID,
    body: TransactionIn,
) -> dict[str, Any]:
    p = ps.get_portfolio(session, user, portfolio_id)
    tx = ps.update_transaction(session, p, tx_id, body.model_dump())
    names = {tx.instrument_id: ps.display_name(md.get_instrument(session, tx.instrument_id))}
    return ps.transaction_out(tx, names)


@router.delete("/{portfolio_id}/transactions/{tx_id}", status_code=204)
def delete_transaction(
    user: UserId, session: DbSession, portfolio_id: uuid.UUID, tx_id: uuid.UUID
) -> Response:
    ps.delete_transaction(session, ps.get_portfolio(session, user, portfolio_id), tx_id)
    return Response(status_code=204)


@router.get("/{portfolio_id}/transactions.csv", summary="Export the ledger as CSV")
def export_csv(user: UserId, session: DbSession, portfolio_id: uuid.UUID) -> Response:
    p = ps.get_portfolio(session, user, portfolio_id)
    return Response(
        ps.export_csv(session, p),
        media_type="text/csv",
        headers={"content-disposition": 'attachment; filename="transactions.csv"'},
    )


@router.post(
    "/{portfolio_id}/import",
    summary="Import transactions from CSV (all or nothing)",
    dependencies=[rate_limit("import", 10)],
)
def import_csv(
    user: UserId, session: DbSession, portfolio_id: uuid.UUID, body: CsvImport
) -> dict[str, Literal["ok"] | int | bool]:
    p = ps.get_portfolio(session, user, portfolio_id)
    items = ps.parse_csv(session, body.csv)
    ps.add_transactions(session, p, items, commit=not body.dry_run)
    return {"status": "ok", "rows": len(items), "dry_run": body.dry_run}
