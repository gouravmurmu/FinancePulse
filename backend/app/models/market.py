"""Reference and market data. Written only by batch jobs; readable by everyone."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

ASSET_CLASSES = ("equity", "index", "etf", "crypto", "commodity", "fx", "macro")
QUOTE_TYPES = ("live", "delayed", "eod", "historical")
QUALITY = ("ok", "suspect", "rejected")
FREQUENCIES = ("1d",)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} in ({', '.join(repr(v) for v in values)})"


class Instrument(Base):
    __tablename__ = "instruments"
    __table_args__ = (CheckConstraint(_in("asset_class", ASSET_CLASSES), name="asset_class"),)

    # Stable canonical ID, e.g. "eq:us:AAPL", "idx:in:NIFTY50", "crypto:BTC",
    # "metal:XAU:comex-fut". Never reused, never derived from a provider symbol.
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    asset_class: Mapped[str] = mapped_column(String(16))
    exchange: Mapped[str | None] = mapped_column(String(32))
    country: Mapped[str | None] = mapped_column(String(2))
    currency: Mapped[str] = mapped_column(String(3))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    # What the price represents, e.g. "COMEX front-month futures, USD/troy oz".
    price_definition: Mapped[str | None] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class InstrumentAlias(Base):
    """Provider-specific symbols and search aliases for an instrument."""

    __tablename__ = "instrument_aliases"
    __table_args__ = (
        UniqueConstraint("provider", "alias", name="uq_instrument_aliases_provider_alias"),
        Index("ix_instrument_aliases_instrument_id", "instrument_id"),
        Index("ix_instrument_aliases_alias_lower", func.lower(text("alias"))),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    instrument_id: Mapped[str] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"))
    # "yfinance", "coingecko", ... or "search" for human-friendly aliases.
    provider: Mapped[str] = mapped_column(String(32))
    alias: Mapped[str] = mapped_column(String(100))


class MarketObservation(Base):
    """One price bar. Upserts are keyed on (instrument, time, provider, frequency)."""

    __tablename__ = "market_observations"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id",
            "observed_at",
            "provider",
            "frequency",
            name="uq_market_observations_key",
        ),
        CheckConstraint(_in("quote_type", QUOTE_TYPES), name="quote_type"),
        CheckConstraint(_in("quality_status", QUALITY), name="quality_status"),
        CheckConstraint(_in("frequency", FREQUENCIES), name="frequency"),
        Index(
            "ix_market_observations_lookup",
            "instrument_id",
            "frequency",
            "observed_at",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    instrument_id: Mapped[str] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(32))
    frequency: Mapped[str] = mapped_column(String(8), default="1d")
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    currency: Mapped[str] = mapped_column(String(3))
    open: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    high: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    low: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    close: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    adj_close: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    volume: Mapped[Decimal | None] = mapped_column(Numeric(28, 4))
    quote_type: Mapped[str] = mapped_column(String(16))
    quality_status: Mapped[str] = mapped_column(String(16), default="ok", server_default="ok")
    # Adjustment and provenance notes, e.g. {"adjusted": "splits+dividends"}.
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
