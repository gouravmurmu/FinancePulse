# Models and evaluation

MarketPulse shows forecasts only next to an honest record of how the same
models did on past data. Most of the time, for most assets, no simple model
predicts prices better than "no change", and the app says so.

## Forecast baselines (`baselines-1`)
Code: `backend/app/analytics/forecast.py`, job `backend/jobs/run_forecasts.py`
(daily at 23:15 UTC, after the evening data refresh).

**Target.** The log return over the next *h* trading days, from the last daily
close, for h = 5 (about a week) and h = 20 (about a month). Prices are each
asset's stored daily closes in its trading currency.

**Models.**
| Model | Prediction |
|---|---|
| No change (persistence) | 0: the price stays where it is. This is the baseline. |
| Historical drift | Average daily log return over the training window × h |
| Damped-trend exponential smoothing | Holt's additive trend with damping (statsmodels `ExponentialSmoothing`) fitted on log prices; h-step forecast minus the last value |

**Training window.** The latest 504 trading days (about two years) before each
forecast origin. Models are refitted at every origin.

**Walk-forward evaluation.** 60 origins, 5 trading days apart, ending h days
before the latest close. At each origin a model sees only data up to that day
(no shuffling, no look-ahead), predicts the next h days, and is scored on what
actually happened. A unit test feeds the models through a spy and checks that
no window ever ends after its origin.

**Metrics** (all on the h-day log return, shown as percentages):
- MAE (average absolute error) and RMSE (weighs large misses more).
- Directional accuracy: share of windows where the predicted direction matched
  the actual one (not defined for "no change"). Shown next to the share of
  windows that ended higher, which is what always guessing "up" would score.
- Error vs no change: MAE(model) / MAE(no change) − 1.

**Beating the baseline.** A model is used only if its MAE is lower than the
no-change MAE *and* a one-sided Diebold-Mariano test on absolute errors gives
p < 0.10, with a Newey-West variance (lag ⌈h/5⌉ − 1) because 20-day windows
taken 5 days apart overlap. Otherwise the app shows "Model did not beat
baseline" and no point forecast.

**Prediction interval.** 80%: the point forecast plus the 10th and 90th
percentiles of the chosen model's walk-forward errors. These are empirical
ranges from 60 recent windows; they are not guaranteed to hold in a regime
that differs from the past two years.

**Unavailable.** Assets with fewer than 824 daily closes (training window +
evaluation span + horizon) get "Forecast unavailable".

**Stored per run** (`forecast_runs`, public read): instrument, horizon, as-of
date, model version, chosen model, whether it beat the baseline, last close,
point and interval, training start, evaluation span, per-model metrics and
p-values, and the time the run was created. Re-runs upsert on (instrument,
horizon, as-of date, model version).

**Not used yet.** XGBoost or other machine-learning models. The plan is to add
them only if the baselines are in place and a model can beat them under the same
walk-forward test.

## Anomalies
See `docs/METHODOLOGY.md#anomalies`. They are statistical flags, not models of
future prices.

## Limits
These are research aids, not advice. Daily closes ignore dividends, intraday
moves and events after the last close. Past error rates can change quickly.
