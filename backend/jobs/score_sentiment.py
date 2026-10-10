"""Classify unscored headlines with FinBERT (ProsusAI/finbert) on CPU.

    python -m jobs.score_sentiment --limit 2000

Needs requirements/ml.txt. Labels are positive, neutral or negative with the
model's probabilities; they describe the headline's tone, not the asset.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.core.logging import configure_logging
from app.db.session import _session_factory
from app.services import market_store, news_service

logger = logging.getLogger("jobs.score_sentiment")
JOB = "score_sentiment"
MODEL = "ProsusAI/finbert"
BATCH = 32

Classifier = Callable[[list[str]], list[dict[str, float]]]


def finbert() -> Classifier:
    from transformers import pipeline  # heavy; only in the ML job

    clf = pipeline("text-classification", model=MODEL, top_k=None, truncation=True)

    def run(texts: list[str]) -> list[dict[str, float]]:
        out = clf(texts, batch_size=BATCH)
        return [{d["label"].lower(): float(d["score"]) for d in row} for row in out]

    return run


def score(session: Any, classify: Classifier, limit: int, model: str = MODEL) -> int:
    articles = news_service.unscored(session, limit)
    done = 0
    for i in range(0, len(articles), BATCH):
        chunk = articles[i : i + BATCH]
        probs = classify([a.headline for a in chunk])
        now = datetime.now(UTC)
        for a, p in zip(chunk, probs, strict=True):
            label = max(p, key=lambda k: p[k])
            a.sentiment_label = label
            a.sentiment_score = round(p[label], 5)
            a.sentiment_probs = {k: round(v, 5) for k, v in p.items()}
            a.sentiment_model = model
            a.scored_at = now
        session.commit()
        done += len(chunk)
    return done


def run(limit: int) -> int:
    factory = _session_factory()
    if factory is None:
        logger.error("DATABASE_URL is not set")
        return 2
    with factory() as session:
        job = market_store.start_job(session, JOB)
        session.commit()
        try:
            n = score(session, finbert(), limit)
            market_store.finish_job(session, job, "success", {"scored": n, "model": MODEL})
        except Exception as exc:
            session.rollback()
            market_store.finish_job(session, job, "failed", {"error": str(exc)[:300]})
            logger.exception("score_failed")
            return 1
        logger.info("done", extra={"scored": n})
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=2000)
    args = parser.parse_args(argv)
    configure_logging("INFO")
    return run(args.limit)


if __name__ == "__main__":
    sys.exit(main())
