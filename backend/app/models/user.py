"""User-owned data. Every table here has Row Level Security keyed on auth.uid()."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = (
        CheckConstraint("base_currency in ('USD', 'INR')", name="base_currency"),
        CheckConstraint("region in ('global', 'india')", name="region"),
    )

    # Same UUID as auth.users.id (foreign key added in the migration, since
    # auth.users is managed by Supabase, not by this metadata).
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    display_name: Mapped[str | None] = mapped_column(String(100))
    base_currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    region: Mapped[str] = mapped_column(String(8), default="global", server_default="global")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
