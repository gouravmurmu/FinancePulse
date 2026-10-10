"""Forecast runs: computed by jobs/run_forecasts.py, served as stored."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.analytics import forecast as fc
from app.models import ForecastRun
from app.services import market_data as md

# Keep enough history for the training window plus the evaluation stretch.
HISTORY_DAYS = 4 * 365
# A stored run older than this is shown as stale rather than current.
STALE_AFTER_DAYS = 7


def compute_and_store(session: Session, inst: md.InstrumentInfo) -> int:
    start = datetime.now(UTC).date() - timedelta(days=HISTORY_DAYS)
    bars = md.load_bars(session, inst.id, start)
    if bars.empty:
        return 0
    results = fc.walk_forward(bars["close"])
    for r in results:
        metrics = {
            "models": {
                m: {
                    "mae": s.mae,
                    "rmse": s.rmse,
                    "directional_accuracy": s.directional_accuracy,
                    "n": s.n,
                    "p_value": s.p_value,
                }
                for m, s in r.scores.items()
            },
            "skill": r.skill,
            "up_share": r.up_share,
            "significance": fc.SIGNIFICANCE,
            "train_window": fc.TRAIN_WINDOW,
        }
        row = {
            "instrument_id": inst.id,
            "horizon_days": r.horizon,
            "as_of": r.as_of,
            "model_version": fc.MODEL_VERSION,
            "best_model": r.best_model,
            "beats_baseline": r.beats_baseline,
            "last_close": r.last_close,
            "point": r.point,
            "lower": r.lower,
            "upper": r.upper,
            "interval": fc.INTERVAL,
            "train_start": r.train_start,
            "eval_start": r.eval_start,
            "eval_end": r.eval_end,
            "metrics": metrics,
        }
        stmt = insert(ForecastRun).values(row)
        session.execute(
            stmt.on_conflict_do_update(
                constraint="uq_forecast_runs_key",
                set_={k: stmt.excluded[k] for k in row if k not in ("instrument_id",)},
            )
        )
    return len(results)


def _run_out(r: ForecastRun) -> dict[str, Any]:
    m = r.metrics
    last = float(r.last_close)
    return {
        "horizon_days": r.horizon_days,
        "as_of": r.as_of.isoformat(),
        "model_version": r.model_version,
        "best_model": r.best_model,
        "best_model_label": fc.MODEL_LABELS.get(r.best_model, r.best_model),
        "beats_baseline": r.beats_baseline,
        "last_close": last,
        "point": float(r.point),
        "lower": float(r.lower),
        "upper": float(r.upper),
        "change_pct": float(r.point) / last - 1 if last else None,
        "interval": float(r.interval),
        "train_start": r.train_start.isoformat(),
        "eval_start": r.eval_start.isoformat(),
        "eval_end": r.eval_end.isoformat(),
        "skill": m.get("skill"),
        "up_share": m.get("up_share"),
        "significance": m.get("significance"),
        "models": [
            {"model": k, "label": fc.MODEL_LABELS.get(k, k), **v}
            for k, v in m.get("models", {}).items()
        ],
        "created_at": r.created_at,
    }


def latest(session: Session, inst: md.InstrumentInfo) -> dict[str, Any]:
    runs = session.scalars(
        select(ForecastRun)
        .where(ForecastRun.instrument_id == inst.id)
        .order_by(ForecastRun.as_of.desc(), ForecastRun.created_at.desc())
        .limit(10)
    ).all()
    by_h: dict[int, ForecastRun] = {}
    for r in runs:
        by_h.setdefault(r.horizon_days, r)
    horizons = [_run_out(by_h[h]) for h in sorted(by_h)]
    today = datetime.now(UTC).date()
    stale = bool(horizons) and all((today - r.as_of).days > STALE_AFTER_DAYS for r in by_h.values())
    reason = None
    if not horizons:
        reason = (
            "Forecast unavailable: not enough price history yet, or the forecast job has "
            "not run for this asset."
        )
    return {
        "instrument_id": inst.id,
        "currency": inst.currency,
        "available": bool(horizons),
        "stale": stale,
        "reason": reason,
        "horizons": horizons,
    }
