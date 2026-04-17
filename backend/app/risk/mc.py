"""Cholesky-correlated Monte-Carlo path simulator + fan-chart builder."""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import pandas as pd

from app.core.config import settings
from app.risk.correlation import cholesky_factor, correlation_matrix
from app.risk.types import FanChartResult

_DEFAULT_PERCENTILES: tuple[int, ...] = (5, 25, 50, 75, 95)


def simulate_correlated_paths(
    mu: np.ndarray,
    sigma: np.ndarray,
    corr: np.ndarray,
    n_paths: int,
    n_steps: int,
    dt: float,
    seed: int | None,
) -> np.ndarray:
    """Simulate `n_paths` GBM paths of `n_steps` with correlated shocks.

    Returns an array of shape `(n_paths, n_steps, N)` where entry
    `[p, t, i]` is the *log* price level of factor `i` at step `t` along
    path `p` (factor starts at 0.0 and drifts).
    """
    n_factors = len(mu)
    if sigma.shape != (n_factors,):
        raise ValueError(f"sigma shape {sigma.shape} != ({n_factors},)")
    if corr.shape != (n_factors, n_factors):
        raise ValueError(f"corr shape {corr.shape} != ({n_factors}, {n_factors})")

    rng_seed = settings.MC_SEED if seed is None else seed
    rng = np.random.default_rng(rng_seed)
    L = cholesky_factor(corr)

    # draws[path, step, factor] = i.i.d. N(0,1)
    z = rng.standard_normal(size=(n_paths, n_steps, n_factors))
    # Correlate each step's vector: shocks = z @ L.T
    correlated_shocks = z @ L.T

    drift = (mu - 0.5 * sigma**2) * dt
    vol_scale = sigma * np.sqrt(dt)
    # per-step log-return = drift + vol_scale * correlated_shock
    step_log_returns = drift + vol_scale * correlated_shocks
    # cumulative log price along time axis (axis=1)
    cumulative = np.cumsum(step_log_returns, axis=1)
    return cumulative


def fan_chart_paths(
    weights: dict[str, Decimal],
    returns: pd.DataFrame,
    horizon_days: int = 10,
    n_paths: int = 10_000,
    seed: int | None = None,
    percentiles: tuple[int, ...] = _DEFAULT_PERCENTILES,
) -> FanChartResult:
    """Simulate portfolio P&L over `horizon_days` and return percentile bands.

    Drift `mu` is set to zero (VaR-style interpretation: we care about the
    shape of the distribution, not the expected path). `sigma` + `corr` are
    estimated from the historical returns DataFrame.
    """
    if returns.empty:
        raise ValueError("returns DataFrame is empty")

    rng_seed = settings.MC_SEED if seed is None else seed
    cols = list(returns.columns)
    sigma_vec = returns.std().to_numpy(dtype=float)
    corr, _ = correlation_matrix(returns)
    mu = np.zeros_like(sigma_vec)

    log_paths = simulate_correlated_paths(
        mu=mu,
        sigma=sigma_vec,
        corr=corr,
        n_paths=n_paths,
        n_steps=horizon_days,
        dt=1.0,
        seed=rng_seed,
    )
    # Convert log-price level to cumulative simple return: exp(x) - 1
    cumulative_simple = np.expm1(log_paths)

    weight_vec = np.array([float(weights.get(c, Decimal(0))) for c in cols], dtype=float)
    # pnl[path, step] = cumulative_simple[path, step, :] @ weight_vec
    pnl = cumulative_simple @ weight_vec

    out: dict[int, list[Decimal]] = {}
    for q in percentiles:
        per_day = np.percentile(pnl, q, axis=0)
        out[q] = [Decimal(str(float(x))) for x in per_day]

    return FanChartResult(
        percentiles=out,
        horizon_days=horizon_days,
        n_paths=n_paths,
        seed=rng_seed,
    )
