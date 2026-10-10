"""Stored forecast runs (public, written by the forecast job)."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ForecastRun(Base):
    __tablename__ = "forecast_runs"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id", "horizon_days", "as_of", "model_version", name="uq_forecast_runs_key"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    instrument_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("instruments.id", ondelete="CASCADE"), index=True
    )
    horizon_days: Mapped[int] = mapped_column(Integer)
    as_of: Mapped[date] = mapped_column(Date)  # last close used
    model_version: Mapped[str] = mapped_column(String(32))
    best_model: Mapped[str] = mapped_column(String(16))
    beats_baseline: Mapped[bool] = mapped_column(Boolean)
    last_close: Mapped[float] = mapped_column(Numeric(28, 10))
    point: Mapped[float] = mapped_column(Numeric(28, 10))
    lower: Mapped[float] = mapped_column(Numeric(28, 10))
    upper: Mapped[float] = mapped_column(Numeric(28, 10))
    interval: Mapped[float] = mapped_column(Numeric(4, 3))
    train_start: Mapped[date] = mapped_column(Date)
    eval_start: Mapped[date] = mapped_column(Date)
    eval_end: Mapped[date] = mapped_column(Date)
    # Per-model MAE, RMSE, directional accuracy, n and p-value; plus skill and up share.
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
