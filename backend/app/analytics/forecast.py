"""Baseline price forecasts with walk-forward evaluation.

Everything works on log prices, so a forecast is a predicted log return over
`h` trading days. Models are refitted at every evaluation origin using only
data up to that origin (no look-ahead), and scored on what happened next.
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

MODEL_VERSION = "baselines-1"
MODELS = ("naive", "drift", "ets")
MODEL_LABELS = {
    "naive": "No change (persistence)",
    "drift": "Historical drift",
    "ets": "Damped-trend exponential smoothing",
}
HORIZONS = (5, 20)
TRAIN_WINDOW = 504  # about two years of trading days
EVAL_ORIGINS = 60
EVAL_STEP = 5
INTERVAL = 0.8  # central prediction interval
# A model "beats the baseline" only if its lower error is unlikely to be luck:
# one-sided Diebold-Mariano test on absolute errors at this level.
SIGNIFICANCE = 0.10
MIN_HISTORY = TRAIN_WINDOW + EVAL_STEP * EVAL_ORIGINS + max(HORIZONS)

Predictor = Callable[[np.ndarray, int], float]


def predict_naive(y: np.ndarray, h: int) -> float:
    return 0.0


def predict_drift(y: np.ndarray, h: int) -> float:
    return float((y[-1] - y[0]) / (len(y) - 1) * h)


def predict_ets(y: np.ndarray, h: int) -> float:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = ExponentialSmoothing(
            y, trend="add", damped_trend=True, initialization_method="estimated"
        ).fit()
        path = fit.forecast(h)
    out = float(path[-1] - y[-1])
    return out if math.isfinite(out) else 0.0


PREDICTORS: dict[str, Predictor] = {
    "naive": predict_naive,
    "drift": predict_drift,
    "ets": predict_ets,
}


@dataclass
class ModelScore:
    mae: float
    rmse: float
    directional_accuracy: float | None
    n: int
    p_value: float | None = None  # vs naive; small means reliably better


def dm_p_value(e_model: np.ndarray, e_base: np.ndarray, lags: int) -> float | None:
    """One-sided Diebold-Mariano test that the model's absolute errors are
    smaller than the baseline's, with a Newey-West variance for overlapping
    windows. Returns None when the loss difference has no variance."""
    d = np.abs(e_model) - np.abs(e_base)
    n = len(d)
    dc = d - d.mean()
    var = float(np.dot(dc, dc) / n)
    for k in range(1, min(lags, n - 1) + 1):
        var += 2 * (1 - k / (lags + 1)) * float(np.dot(dc[k:], dc[:-k]) / n)
    if var <= 0:
        return None
    stat = float(d.mean()) / math.sqrt(var / n)
    return 0.5 * (1 + math.erf(stat / math.sqrt(2)))


@dataclass
class HorizonResult:
    horizon: int
    as_of: date
    last_close: float
    train_start: date
    eval_start: date
    eval_end: date
    scores: dict[str, ModelScore]
    best_model: str
    beats_baseline: bool
    skill: float | None  # 1 - MAE(model) / MAE(naive) for the best non-naive model
    up_share: float  # share of evaluation windows that ended higher
    point: float
    lower: float
    upper: float
    errors: dict[str, list[float]] = field(default_factory=dict, repr=False)


def _score(pred: np.ndarray, actual: np.ndarray, directional: bool) -> ModelScore:
    err = pred - actual
    da = None
    if directional:
        moving = pred != 0
        if moving.any():
            da = float(np.mean(np.sign(pred[moving]) == np.sign(actual[moving])))
    return ModelScore(
        mae=float(np.mean(np.abs(err))),
        rmse=float(np.sqrt(np.mean(err**2))),
        directional_accuracy=da,
        n=len(err),
    )


def walk_forward(
    close: pd.Series,
    horizons: tuple[int, ...] = HORIZONS,
    models: tuple[str, ...] = MODELS,
    train_window: int = TRAIN_WINDOW,
    origins: int = EVAL_ORIGINS,
    step: int = EVAL_STEP,
) -> list[HorizonResult]:
    """Evaluate each model on the last `origins` time-ordered windows, then
    forecast from the latest close. Returns [] when history is too short."""
    close = close.dropna().astype(float)
    close = close[close > 0]
    if len(close) < train_window + step * origins + max(horizons):
        return []
    y = np.log(close.to_numpy())
    idx = close.index
    n = len(y)
    out: list[HorizonResult] = []
    cache: dict[tuple[str, int, int], float] = {}

    def predict(model: str, end: int, h: int) -> float:
        key = (model, end, h)
        if key not in cache:
            cache[key] = PREDICTORS[model](y[end - train_window + 1 : end + 1], h)
        return cache[key]

    for h in horizons:
        # Origins are the last observed index; the target is h bars later.
        ends = [n - 1 - h - step * k for k in range(origins)][::-1]
        actual = np.array([y[e + h] - y[e] for e in ends])
        preds = {m: np.array([predict(m, e, h) for e in ends]) for m in models}
        scores = {m: _score(preds[m], actual, m != "naive") for m in models}
        errors = {m: (actual - preds[m]).tolist() for m in models}
        # Windows overlap when the horizon is longer than the step between origins.
        lags = max(0, math.ceil(h / step) - 1)
        for m in models:
            if m != "naive":
                scores[m].p_value = dm_p_value(np.array(errors[m]), np.array(errors["naive"]), lags)
        challengers = [m for m in models if m != "naive"]
        top = min(challengers, key=lambda m: scores[m].mae) if challengers else None
        naive_mae = scores["naive"].mae
        skill = 1 - scores[top].mae / naive_mae if top and naive_mae else None
        p = scores[top].p_value if top else None
        wins = top is not None and p is not None and p < SIGNIFICANCE and (skill or 0) > 0
        best = top if wins and top else "naive"
        # Interval from the chosen model's own out-of-sample errors.
        lo_q, hi_q = np.quantile(errors[best], [(1 - INTERVAL) / 2, (1 + INTERVAL) / 2])
        point_lr = predict(best, n - 1, h)
        last = float(close.iloc[-1])
        out.append(
            HorizonResult(
                horizon=h,
                as_of=idx[-1].date(),
                last_close=last,
                train_start=idx[n - train_window].date(),
                eval_start=idx[ends[0]].date(),
                eval_end=idx[ends[-1] + h].date(),
                scores=scores,
                best_model=best,
                beats_baseline=best != "naive",
                skill=skill,
                up_share=float(np.mean(actual > 0)),
                point=last * math.exp(point_lr),
                lower=last * math.exp(point_lr + lo_q),
                upper=last * math.exp(point_lr + hi_q),
                errors=errors,
            )
        )
    return out
