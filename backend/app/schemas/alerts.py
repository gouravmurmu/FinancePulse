"""Request models for alerts."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field

RuleKind = Literal["price_above", "price_below", "move_pct", "volatility_above", "anomaly"]


class AlertRuleCreate(BaseModel):
    instrument_id: str = Field(min_length=1, max_length=64)
    kind: RuleKind
    # Price in the instrument's currency, or a fraction (0.05 = 5%) for move and volatility.
    threshold: float | None = None


class AlertRuleUpdate(BaseModel):
    threshold: float | None = None
    active: bool | None = None


class MarkRead(BaseModel):
    # Omit to mark everything read.
    ids: list[uuid.UUID] | None = Field(None, max_length=500)
