"""Statistical anomaly flags using robust z-scores (median and MAD).

Every score at date t uses only a trailing window that ends the day before t,
so nothing looks ahead. Flags are statistical: they say a move was unusual for
this instrument, not why it happened. See docs/METHODOLOGY.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

MAD_SCALE = 1.4826  # makes MAD comparable to a standard deviation for normal data
WINDOW = 252
MIN_HISTORY = 120
THRESHOLDS = {"return": 4.0, "volume": 4.0, "volatility": 3.5, "correlation": 3.5}
VOL_WINDOW = 20
CORR_WINDOW = 60
# Calendar days between flags that still count as the same episode.
EPISODE_GAP_DAYS = {"volatility": 10, "correlation": 20}


@dataclass(frozen=True)
class Anomaly:
    kind: str  # return | volume | volatility | correlation
    observed_at: date
    value: float
    baseline: float
    zscore: float
    threshold: float


def robust_z(series: pd.Series, window: int = WINDOW, min_history: int = MIN_HISTORY) -> pd.Series:
    """(x_t - median) / (1.4826 * MAD), both over the `window` values before t."""
    past = series.shift(1)
    med = past.rolling(window, min_periods=min_history).median()
    mad = past.rolling(window, min_periods=min_history).apply(
        lambda w: np.median(np.abs(w - np.median(w))), raw=True
    )
    scale = MAD_SCALE * mad
    z = (series - med) / scale.where(scale > 1e-12)
    return z


def _flags(kind: str, value: pd.Series, z: pd.Series, baseline: pd.Series) -> list[Anomaly]:
    thr = THRESHOLDS[kind]
    hit = z.abs() >= thr
    out = []
    for d in z.index[hit.fillna(False)]:
        out.append(
            Anomaly(
                kind=kind,
                observed_at=d.date(),
                value=float(value.loc[d]),
                baseline=float(baseline.loc[d]),
                zscore=float(z.loc[d]),
                threshold=thr,
            )
        )
    return out


def detect(
    close: pd.Series,
    volume: pd.Series | None = None,
    benchmark_close: pd.Series | None = None,
    since: date | None = None,
) -> list[Anomaly]:
    """Scan one instrument's daily closes (and volume) for unusual days."""
    close = close.dropna().astype(float)
    if len(close) < MIN_HISTORY + 2:
        return []
    rets = close.pct_change().dropna()
    found: list[Anomaly] = []

    z = robust_z(rets)
    found += _flags(
        "return", rets, z, rets.shift(1).rolling(WINDOW, min_periods=MIN_HISTORY).median()
    )

    if volume is not None:
        vol = volume.reindex(close.index).astype(float)
        vol = vol[vol > 0]
        if len(vol) > MIN_HISTORY + 2:
            lv = np.log(vol)
            zv = robust_z(lv)
            base = np.exp(lv.shift(1).rolling(WINDOW, min_periods=MIN_HISTORY).median())
            found += [a for a in _flags("volume", vol, zv, base) if a.zscore > 0]

    rv = rets.rolling(VOL_WINDOW).std()
    zr = robust_z(rv.dropna())
    base_rv = rv.shift(1).rolling(WINDOW, min_periods=MIN_HISTORY).median()
    found += [
        a for a in _flags("volatility", rv.dropna(), zr, base_rv.reindex(zr.index)) if a.zscore > 0
    ]

    if benchmark_close is not None:
        b = benchmark_close.dropna().astype(float).reindex(close.index).ffill()
        br = b.pct_change()
        both = pd.concat([rets, br], axis=1, keys=["a", "b"], sort=True).dropna()
        if len(both) > CORR_WINDOW + MIN_HISTORY:
            corr = both["a"].rolling(CORR_WINDOW).corr(both["b"]).dropna()
            # Change in correlation over one window: a regime shift, not a single day.
            dcorr = corr - corr.shift(CORR_WINDOW)
            zc = robust_z(dcorr.dropna())
            found += _flags(
                "correlation", corr.reindex(zc.index), zc, corr.shift(CORR_WINDOW).reindex(zc.index)
            )

    # Flags on nearby days describe one episode: keep only its first day. The
    # gap is measured from the previous flagged day, so a long episode stays one.
    found.sort(key=lambda a: (a.kind, a.observed_at))
    deduped: list[Anomaly] = []
    prev: Anomaly | None = None
    for a in found:
        gap = EPISODE_GAP_DAYS.get(a.kind)
        same_episode = (
            prev is not None
            and gap is not None
            and prev.kind == a.kind
            and (a.observed_at - prev.observed_at).days <= gap
        )
        if not same_episode:
            deduped.append(a)
        prev = a
    # Filter after grouping so a re-scan never re-flags an episode that began earlier.
    if since is not None:
        deduped = [a for a in deduped if a.observed_at >= since]
    return sorted(deduped, key=lambda a: a.observed_at)
