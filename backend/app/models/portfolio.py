"""Portfolios, transaction ledger and watchlists. Owner-only (RLS on user_id)."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SIDES = ("buy", "sell")
# How a quantity is measured. Physical metal is held by weight and valued from
# the per-troy-ounce reference price; everything else counts units/shares.
UNITS = ("unit", "troy_oz", "gram")


class Portfolio(Base):
    __tablename__ = "portfolios"
    __table_args__ = (
        CheckConstraint("base_currency in ('USD', 'INR')", name="base_currency"),
        UniqueConstraint("user_id", "name", name="uq_portfolios_user_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    name: Mapped[str] = mapped_column(String(80))
    base_currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    benchmark_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("instruments.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("side in ('buy', 'sell')", name="side"),
        CheckConstraint("unit in ('unit', 'troy_oz', 'gram')", name="unit"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("price >= 0", name="price_non_negative"),
        CheckConstraint("fees >= 0", name="fees_non_negative"),
        CheckConstraint("currency in ('USD', 'INR')", name="currency"),
        Index("ix_transactions_portfolio_date", "portfolio_id", "trade_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    instrument_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("instruments.id", ondelete="RESTRICT")
    )
    side: Mapped[str] = mapped_column(String(4))
    trade_date: Mapped[date] = mapped_column(Date)
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 10))
    unit: Mapped[str] = mapped_column(String(8), default="unit", server_default="unit")
    # Price per unit of `unit`, in `currency` (the instrument's trading currency).
    price: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    fees: Mapped[Decimal] = mapped_column(Numeric(24, 8), default=0, server_default="0")
    currency: Mapped[str] = mapped_column(String(3))
    notes: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Watchlist(Base):
    __tablename__ = "watchlists"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_watchlists_user_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    name: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint("watchlist_id", "instrument_id", name="uq_watchlist_items_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    watchlist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("watchlists.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    instrument_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("instruments.id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
