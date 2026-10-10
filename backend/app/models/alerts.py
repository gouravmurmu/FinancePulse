"""Anomaly flags (public, written by the scan job) and user alerts (owner-only)."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

ANOMALY_KINDS = ("return", "volume", "volatility", "correlation")
ALERT_KINDS = ("price_above", "price_below", "move_pct", "volatility_above", "anomaly")


class AnomalyFlag(Base):
    __tablename__ = "anomalies"
    __table_args__ = (
        UniqueConstraint("instrument_id", "observed_at", "kind", name="uq_anomalies_key"),
        CheckConstraint("kind in ('return', 'volume', 'volatility', 'correlation')", name="kind"),
        Index("ix_anomalies_observed_at", "observed_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    instrument_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("instruments.id", ondelete="CASCADE"), index=True
    )
    observed_at: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(16))
    value: Mapped[Decimal] = mapped_column(Numeric(28, 10))
    baseline: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
    zscore: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    threshold: Mapped[Decimal] = mapped_column(Numeric(8, 3))
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AlertRule(Base):
    __tablename__ = "alert_rules"
    __table_args__ = (
        CheckConstraint(
            "kind in ('price_above', 'price_below', 'move_pct', 'volatility_above', 'anomaly')",
            name="kind",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    instrument_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("instruments.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(20))
    # Price in the instrument's currency, or a fraction for move/volatility rules.
    threshold: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # Whether the condition held at the last evaluation, so rules fire on crossing.
    last_state: Mapped[bool | None] = mapped_column(Boolean)
    last_evaluated_on: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AlertEvent(Base):
    __tablename__ = "alert_events"
    __table_args__ = (
        UniqueConstraint("rule_id", "observed_at", name="uq_alert_events_rule_date"),
        Index("ix_alert_events_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alert_rules.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    instrument_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("instruments.id", ondelete="CASCADE")
    )
    observed_at: Mapped[date] = mapped_column(Date)
    message: Mapped[str] = mapped_column(String(300))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
