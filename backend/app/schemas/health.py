from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class DatabaseHealth(BaseModel):
    status: Literal["ok", "unavailable", "not_configured"]
    latency_ms: float | None


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    environment: str
    server_time: datetime
    database: DatabaseHealth
