"""Request and response models for portfolios, transactions and watchlists."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Currency = Literal["USD", "INR"]
Name = Field(min_length=1, max_length=80)


class PortfolioCreate(BaseModel):
    name: str = Name
    base_currency: Currency = "USD"
    benchmark_id: str | None = Field(None, max_length=64)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name can't be blank")
        return v.strip()


class PortfolioUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    base_currency: Currency | None = None
    benchmark_id: str | None = Field(None, max_length=64)


class PortfolioOut(BaseModel):
    id: uuid.UUID
    name: str
    base_currency: str
    benchmark_id: str | None
    transaction_count: int
    created_at: datetime


class TransactionIn(BaseModel):
    instrument_id: str = Field(max_length=64)
    side: Literal["buy", "sell"]
    trade_date: date
    quantity: Decimal = Field(gt=0, le=Decimal("1e15"), max_digits=28, decimal_places=10)
    unit: Literal["unit", "troy_oz", "gram"] = "unit"
    price: Decimal = Field(ge=0, le=Decimal("1e14"), max_digits=24, decimal_places=8)
    fees: Decimal = Field(Decimal(0), ge=0, le=Decimal("1e14"), max_digits=24, decimal_places=8)
    notes: str | None = Field(None, max_length=200)

    @field_validator("trade_date")
    @classmethod
    def _not_future(cls, v: date) -> date:
        if v > date.today() or v.year < 1970:
            raise ValueError("Trade date must be between 1970 and today")
        return v


class TransactionOut(BaseModel):
    id: uuid.UUID
    instrument_id: str
    name: str
    side: str
    trade_date: date
    quantity: float
    unit: str
    price: float
    fees: float
    currency: str
    notes: str | None


class CsvImport(BaseModel):
    csv: str = Field(min_length=1, max_length=500_000)
    dry_run: bool = False


class PortfolioStressRequest(BaseModel):
    preset: str | None = None
    shocks: dict[str, float] | None = None


class WatchlistCreate(BaseModel):
    name: str = Name


class WatchlistItemIn(BaseModel):
    instrument_id: str = Field(max_length=64)
