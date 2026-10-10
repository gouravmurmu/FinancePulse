"""Headlines (public, written by the news job) and their instrument links."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NewsArticle(Base):
    __tablename__ = "news_articles"
    __table_args__ = (
        UniqueConstraint("provider", "provider_id", name="uq_news_articles_provider_id"),
        Index("ix_news_articles_published_at", "published_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(32))
    provider_id: Mapped[str] = mapped_column(String(200))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(80))
    headline: Mapped[str] = mapped_column(String(400))
    summary: Mapped[str | None] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(String(1000))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # FinBERT classification of the headline; null until the scoring job runs.
    sentiment_label: Mapped[str | None] = mapped_column(String(10))
    sentiment_score: Mapped[float | None] = mapped_column(Numeric(6, 5))
    sentiment_probs: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    sentiment_model: Mapped[str | None] = mapped_column(String(64))
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NewsInstrument(Base):
    __tablename__ = "news_instruments"
    __table_args__ = (Index("ix_news_instruments_instrument", "instrument_id", "article_id"),)

    article_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("news_articles.id", ondelete="CASCADE"), primary_key=True
    )
    instrument_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("instruments.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
