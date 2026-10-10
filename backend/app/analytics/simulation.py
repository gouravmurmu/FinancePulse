"""Monte Carlo simulation and stress tests. Outputs are distributions, not forecasts."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class MonteCarloResult:
    horizon_days: int
    paths: int
    seed: int
    percentiles: dict[int, list[float]]  # percentile -> value per day (day 0 .. horizon)
    final_values: np.ndarray
    probability_of_loss: float


PERCENTILES = (5, 25, 50, 75, 95)


def monte_carlo(
    initial_value: float,
    weights: np.ndarray,
    mean_returns: np.ndarray,
    cov: np.ndarray,
    horizon_days: int,
    paths: int = 2000,
    seed: int = 42,
) -> MonteCarloResult:
    """Simulate a fixed-weight portfolio with multivariate normal daily returns.

    Assumptions (also shown in the UI): daily asset returns are i.i.d. normal
    with the given mean vector and covariance matrix (estimated from history),
    weights are rebalanced daily, no fees or taxes.
    """
    if initial_value <= 0:
        raise ValueError("initial_value must be positive")
    if not 1 <= horizon_days <= 2520:
        raise ValueError("horizon_days must be between 1 and 2520")
    if not 100 <= paths <= 20000:
        raise ValueError("paths must be between 100 and 20000")
    weights = np.asarray(weights, dtype=float)
    if not np.isclose(weights.sum(), 1.0):
        raise ValueError("weights must sum to 1")

    rng = np.random.default_rng(seed)
    # Cholesky needs a positive-definite matrix; add a tiny ridge for safety.
    chol = np.linalg.cholesky(cov + np.eye(len(cov)) * 1e-12)
    z = rng.standard_normal((paths, horizon_days, len(weights)))
    asset_returns = mean_returns + z @ chol.T
    portfolio_returns = asset_returns @ weights
    # Simple returns cannot go below -100%.
    portfolio_returns = np.maximum(portfolio_returns, -0.999999)
    growth = np.cumprod(1 + portfolio_returns, axis=1)
    values = np.concatenate([np.ones((paths, 1)), growth], axis=1) * initial_value

    pct = {p: np.percentile(values, p, axis=0).round(4).tolist() for p in PERCENTILES}
    final = values[:, -1]
    return MonteCarloResult(
        horizon_days=horizon_days,
        paths=paths,
        seed=seed,
        percentiles=pct,
        final_values=final,
        probability_of_loss=float(np.mean(final < initial_value)),
    )


def stress_test(weights: dict[str, float], shocks: dict[str, float]) -> dict[str, float]:
    """Instant portfolio impact of per-asset percentage shocks.

    Returns each asset's contribution (weight × shock) and the total. Assets
    without a shock contribute zero.
    """
    contributions = {k: w * shocks.get(k, 0.0) for k, w in weights.items()}
    return {**contributions, "total": float(sum(contributions.values()))}
