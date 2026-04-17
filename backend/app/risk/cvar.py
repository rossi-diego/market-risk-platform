"""Expected Shortfall (CVaR): average loss in the tail beyond VaR.

Invariant: for the same confidence + horizon, CVaR >= VaR.
"""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import pandas as pd
from scipy.stats import norm

from app.core.config import settings
from app.risk.types import CVaRResult, Leg, VaRMethod
from app.risk.var import _leg_weights, _weights_vec


def _tail_mean(samples: np.ndarray, confidence: float) -> float:
    cutoff = np.percentile(samples, (1.0 - confidence) * 100.0)
    tail = samples[samples <= cutoff]
    if tail.size == 0:
        return float(cutoff)
    return float(tail.mean())


def _historical_es(
    returns: pd.DataFrame,
    weights: dict[str, Decimal],
    confidence: Decimal,
    horizon_days: int,
    window: int,
) -> tuple[Decimal, dict[Leg, Decimal], int]:
    df = returns.tail(window) if len(returns) > window else returns
    cols = list(df.columns)
    arr = df.to_numpy()
    if horizon_days > 1:
        arr = np.asarray(
            [arr[i : i + horizon_days].sum(axis=0) for i in range(len(arr) - horizon_days + 1)]
        )

    def _es_for(w: dict[str, Decimal]) -> Decimal:
        pnl = arr @ _weights_vec(w, cols)
        return Decimal(str(abs(_tail_mean(pnl, float(confidence)))))

    flat = _es_for(weights)
    per_leg: dict[Leg, Decimal] = {
        "cbot": _es_for(_leg_weights(weights, "cbot")),
        "basis": _es_for(_leg_weights(weights, "basis")),
        "fx": _es_for(_leg_weights(weights, "fx")),
    }
    return flat, per_leg, len(df)


def _parametric_es(
    returns: pd.DataFrame,
    weights: dict[str, Decimal],
    confidence: Decimal,
    horizon_days: int,
) -> tuple[Decimal, dict[Leg, Decimal], int]:
    """Closed form for N(0, σ_p): ES = φ(z) / (1 - α) × σ_p × sqrt(h)."""
    cols = list(returns.columns)
    cov = returns.cov().to_numpy()
    alpha = float(confidence)
    z = float(norm.ppf(alpha))
    pdf_z = float(norm.pdf(z))
    multiplier = pdf_z / (1.0 - alpha)
    sqrt_h = float(np.sqrt(horizon_days))

    def _es_for(w: dict[str, Decimal]) -> Decimal:
        w_vec = _weights_vec(w, cols)
        variance = float(w_vec @ cov @ w_vec)
        sigma = float(np.sqrt(max(variance, 0.0)))
        return Decimal(str(abs(multiplier * sigma * sqrt_h)))

    flat = _es_for(weights)
    per_leg: dict[Leg, Decimal] = {
        "cbot": _es_for(_leg_weights(weights, "cbot")),
        "basis": _es_for(_leg_weights(weights, "basis")),
        "fx": _es_for(_leg_weights(weights, "fx")),
    }
    return flat, per_leg, len(returns)


def _monte_carlo_es(
    returns: pd.DataFrame,
    weights: dict[str, Decimal],
    confidence: Decimal,
    horizon_days: int,
    n_paths: int,
    seed: int | None,
) -> tuple[Decimal, dict[Leg, Decimal], int, int]:
    rng_seed = settings.MC_SEED if seed is None else seed
    rng = np.random.default_rng(rng_seed)
    cols = list(returns.columns)
    mu = returns.mean().to_numpy()
    cov = returns.cov().to_numpy()
    samples = rng.multivariate_normal(mu, cov, size=(n_paths, horizon_days)).sum(axis=1)

    def _es_for(w: dict[str, Decimal]) -> Decimal:
        pnl = samples @ _weights_vec(w, cols)
        return Decimal(str(abs(_tail_mean(pnl, float(confidence)))))

    flat = _es_for(weights)
    per_leg: dict[Leg, Decimal] = {
        "cbot": _es_for(_leg_weights(weights, "cbot")),
        "basis": _es_for(_leg_weights(weights, "basis")),
        "fx": _es_for(_leg_weights(weights, "fx")),
    }
    return flat, per_leg, len(returns), rng_seed


def expected_shortfall(
    returns: pd.DataFrame,
    weights: dict[str, Decimal],
    confidence: Decimal = Decimal("0.975"),
    horizon_days: int = 1,
    method: VaRMethod = "historical",
    window: int = 252,
    n_paths: int = 10_000,
    seed: int | None = None,
) -> CVaRResult:
    if returns.empty:
        raise ValueError("returns DataFrame is empty")

    if method == "historical":
        flat, per_leg, n = _historical_es(returns, weights, confidence, horizon_days, window)
        return CVaRResult(
            method="historical",
            confidence=confidence,
            horizon_days=horizon_days,
            value_brl=flat,
            per_leg=per_leg,
            n_observations=n,
        )
    if method == "parametric":
        flat, per_leg, n = _parametric_es(returns, weights, confidence, horizon_days)
        return CVaRResult(
            method="parametric",
            confidence=confidence,
            horizon_days=horizon_days,
            value_brl=flat,
            per_leg=per_leg,
            n_observations=n,
        )
    # monte_carlo
    flat, per_leg, n, used_seed = _monte_carlo_es(
        returns, weights, confidence, horizon_days, n_paths, seed
    )
    return CVaRResult(
        method="monte_carlo",
        confidence=confidence,
        horizon_days=horizon_days,
        value_brl=flat,
        per_leg=per_leg,
        n_observations=n,
        seed=used_seed,
    )
