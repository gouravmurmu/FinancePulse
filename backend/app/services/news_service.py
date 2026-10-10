"""Headlines and FinBERT sentiment: written by jobs, served as stored."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import NewsArticle, NewsInstrument
from app.providers import finnhub
from app.providers.finnhub import NewsItem
from app.services import market_data as md

TREND_DAYS = 90


def store_items(session: Session, items: list[NewsItem], retrieved_at: datetime) -> tuple[int, int]:
    """Upsert headlines and their instrument links. Returns (new articles, new links)."""
    new_articles = new_links = 0
    for item in items:
        row = session.execute(
            insert(NewsArticle)
            .values(
                provider=finnhub.PROVIDER,
                provider_id=item.provider_id[:200],
                published_at=item.published_at,
                source=item.source,
                headline=item.headline,
                summary=item.summary,
                url=item.url,
                retrieved_at=retrieved_at,
            )
            .on_conflict_do_nothing(constraint="uq_news_articles_provider_id")
            .returning(NewsArticle.id)
        ).first()
        article_id: int | None
        if row is not None:
            article_id = row[0]
            new_articles += 1
        else:
            article_id = session.scalar(
                select(NewsArticle.id).where(
                    NewsArticle.provider == finnhub.PROVIDER,
                    NewsArticle.provider_id == item.provider_id[:200],
                )
            )
        if article_id is None:
            continue
        for iid in sorted(item.instrument_ids):
            new_links += len(
                session.execute(
                    insert(NewsInstrument)
                    .values(article_id=article_id, instrument_id=iid)
                    .on_conflict_do_nothing()
                    .returning(NewsInstrument.article_id)
                ).all()
            )
    return new_articles, new_links


def unscored(session: Session, limit: int) -> list[NewsArticle]:
    return list(
        session.scalars(
            select(NewsArticle)
            .where(NewsArticle.sentiment_label.is_(None))
            .order_by(NewsArticle.published_at.desc())
            .limit(limit)
        )
    )


def _f(x: Any) -> float | None:
    return None if x is None else float(x)


def article_out(a: NewsArticle) -> dict[str, Any]:
    return {
        "id": a.id,
        "published_at": a.published_at,
        "source": a.source,
        "headline": a.headline,
        "summary": a.summary,
        "url": a.url,
        "provider": a.provider,
        "sentiment": None
        if a.sentiment_label is None
        else {
            "label": a.sentiment_label,
            "score": _f(a.sentiment_score),
            "probs": a.sentiment_probs,
            "model": a.sentiment_model,
        },
    }


def coverage_note(inst: md.InstrumentInfo) -> str | None:
    if inst.asset_class in ("equity", "etf") and inst.country == "US":
        return None
    if inst.asset_class == "crypto":
        return "Crypto headlines come from a general crypto feed matched by coin name or ticker."
    return (
        "The free news source covers US-listed stocks, ETFs and major coins only, so there are "
        "no headlines for this asset."
    )


def instrument_news(session: Session, inst: md.InstrumentInfo, limit: int) -> dict[str, Any]:
    articles = session.scalars(
        select(NewsArticle)
        .join(NewsInstrument, NewsInstrument.article_id == NewsArticle.id)
        .where(NewsInstrument.instrument_id == inst.id)
        .order_by(NewsArticle.published_at.desc())
        .limit(limit)
    ).all()
    return {
        "instrument_id": inst.id,
        "configured": finnhub.api_key() is not None or bool(articles),
        "coverage_note": coverage_note(inst),
        "articles": [article_out(a) for a in articles],
        "trend": sentiment_trend(session, inst),
    }


def sentiment_trend(session: Session, inst: md.InstrumentInfo) -> dict[str, Any]:
    """Daily net tone (P(positive) − P(negative), averaged over headlines) next
    to the close. Exploratory only: no causal or predictive claim."""
    since = datetime.now(UTC) - timedelta(days=TREND_DAYS)
    rows = session.execute(
        select(
            func.date(NewsArticle.published_at).label("day"),
            func.count().label("n"),
            func.avg(
                NewsArticle.sentiment_probs["positive"].as_float()
                - NewsArticle.sentiment_probs["negative"].as_float()
            ).label("tone"),
        )
        .join(NewsInstrument, NewsInstrument.article_id == NewsArticle.id)
        .where(
            NewsInstrument.instrument_id == inst.id,
            NewsArticle.published_at >= since,
            NewsArticle.sentiment_probs.is_not(None),
        )
        .group_by("day")
        .order_by("day")
    ).all()
    bars = md.load_bars(session, inst.id, since.date())
    close = bars["close"] if not bars.empty else pd.Series(dtype=float)
    return {
        "days": TREND_DAYS,
        "points": [
            {"date": r.day.isoformat(), "headlines": int(r.n), "tone": round(float(r.tone), 4)}
            for r in rows
            if r.tone is not None
        ],
        "close": [
            {"date": d.date().isoformat(), "value": round(float(v), 6)}
            for d, v in close.dropna().items()
        ],
    }
