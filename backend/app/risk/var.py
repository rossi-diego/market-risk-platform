"""Three Value-at-Risk methods — historical, parametric, Monte Carlo (basic).

Common signature: a DataFrame of factor returns (ZS=F, ZC=F, USDBRL=X), a
`weights` mapping of BRL-denominated exposure per factor (so that P&L_i =
weights[i] * returns[i]), and a confidence / horizon combination. Each method
returns a `VaRResult` with a flat number plus the single-factor ("per-leg")
breakdown. Per-leg sums always >= flat (diversification).

Leg mapping: ZS=F and ZC=F feed the CBOT leg, USDBRL=X feeds the FX leg. The
basis leg is priced off exposure tons directly (no factor return); in the
current Phase 6 scope it contributes zero when only price-factor returns are
available, and is reported as zero in `per_leg`.

Monte Carlo is "basic": multivariate-normal draws from the historical
mean/cov. Phase 7 adds Cholesky-correlated GBM + component VaR.
"""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import pandas as pd
from scipy.stats import norm

from app.core.config import settings
from app.risk.types import Leg, VaRResult

_CBOT_INSTRUMENTS: tuple[str, ...] = ("ZS=F", "ZC=F")
_FX_INSTRUMENTS: tuple[str, ...] = ("USDBRL=X",)


def _weights_vec(weights: dict[str, Decimal], columns: list[str]) -> np.ndarray:
    return np.array([float(weights.get(c, Decimal(0))) for c in columns], dtype=float)


def _z_score(confidence: Decimal) -> float:
    # norm.ppf(confidence) gives the 1-tail z. A 95% VaR uses z_{0.95}.
    return float(norm.ppf(float(confidence)))


def _leg_weights(weights: dict[str, Decimal], leg: Leg) -> dict[str, Decimal]:
    """Return weights isolated to a single leg (others zeroed)."""
    isolated: dict[str, Decimal] = {k: Decimal(0) for k in weights}
    if leg == "cbot":
        keep = _CBOT_INSTRUMENTS
    elif leg == "fx":
        keep = _FX_INSTRUMENTS
    else:  # "basis" — no factor return in the current engine scope
        return isolated
    for k in keep:
        if k in weights:
            isolated[k] = weights[k]
    return isolated


def historical_var(
    returns: pd.DataFrame,
    weights: dict[str, Decimal],
    confidence: Decimal = Decimal("0.95"),
    horizon_days: int = 1,
    window: int = 252,
) -> VaRResult:
    """Historical VaR: percentile of the sampled portfolio P&L distribution.

    For `horizon_days > 1` we use overlapping `h`-day returns (more accurate
    than sqrt-h scaling for fat-tailed empirical distributions).
    """
    if returns.empty:
        raise ValueError("returns DataFrame is empty")
    df = returns.tail(window) if len(returns) > window else returns
    cols = list(df.columns)

    def _flat_var(w: dict[str, Decimal]) -> Decimal:
        w_vec = _weights_vec(w, cols)
        arr = df.to_numpy()
        if horizon_days > 1:
            # Sum h consecutive rows to get overlapping h-day returns.
            arr = np.asarray(
                [arr[i : i + horizon_days].sum(axis=0) for i in range(len(arr) - horizon_days + 1)]
            )
        pnl = arr @ w_vec
        cutoff = np.percentile(pnl, (1.0 - float(confidence)) * 100.0)
        return Decimal(str(abs(float(cutoff))))

    flat = _flat_var(weights)
    per_leg: dict[Leg, Decimal] = {
        "cbot": _flat_var(_leg_weights(weights, "cbot")),
        "basis": _flat_var(_leg_weights(weights, "basis")),
        "fx": _flat_var(_leg_weights(weights, "fx")),
    }

    return VaRResult(
        method="historical",
        confidence=confidence,
        horizon_days=horizon_days,
        value_brl=flat,
        per_leg=per_leg,
        n_observations=len(df),
    )


def parametric_var(
    returns: pd.DataFrame,
    weights: dict[str, Decimal],
    confidence: Decimal = Decimal("0.95"),
    horizon_days: int = 1,
) -> VaRResult:
    """Parametric (delta-normal) VaR.

    `value_brl = z_alpha * sqrt(w' Σ w) * sqrt(horizon)`. Per-leg is the
    same formula with only that leg's weight non-zero; the diversified
    flat is never greater than the sum of the isolated per-leg VaRs.
    """
    if returns.empty:
        raise ValueError("returns DataFrame is empty")
    cols = list(returns.columns)
    cov = returns.cov().to_numpy()
    z = _z_score(confidence)
    sqrt_h = float(np.sqrt(horizon_days))

    def _var_for(w: dict[str, Decimal]) -> Decimal:
        w_vec = _weights_vec(w, cols)
        variance = float(w_vec @ cov @ w_vec)
        sigma_p = float(np.sqrt(max(variance, 0.0)))
        return Decimal(str(abs(z * sigma_p * sqrt_h)))

    flat = _var_for(weights)
    per_leg: dict[Leg, Decimal] = {
        "cbot": _var_for(_leg_weights(weights, "cbot")),
        "basis": _var_for(_leg_weights(weights, "basis")),
        "fx": _var_for(_leg_weights(weights, "fx")),
    }
    return VaRResult(
        method="parametric",
        confidence=confidence,
        horizon_days=horizon_days,
        value_brl=flat,
        per_leg=per_leg,
        n_observations=len(returns),
    )


def monte_carlo_var(
    returns: pd.DataFrame,
    weights: dict[str, Decimal],
    confidence: Decimal = Decimal("0.95"),
    horizon_days: int = 1,
    n_paths: int = 10_000,
    seed: int | None = None,
) -> VaRResult:
    """Monte Carlo VaR by sampling from the empirical mean+cov of returns.

    Reproducible via `seed` (defaults to `settings.MC_SEED`). Same `seed`
    must always produce the same `value_brl` to six decimals.
    """
    if returns.empty:
        raise ValueError("returns DataFrame is empty")
    rng_seed = settings.MC_SEED if seed is None else seed
    rng = np.random.default_rng(rng_seed)

    cols = list(returns.columns)
    mu = returns.mean().to_numpy()
    cov = returns.cov().to_numpy()

    # Sample horizon_days × n_paths, sum within each path to get
    # horizon-total returns per path.
    samples = rng.multivariate_normal(mu, cov, size=(n_paths, horizon_days))
    horizon_returns = samples.sum(axis=1)  # shape (n_paths, n_factors)

    def _var_for(w: dict[str, Decimal]) -> Decimal:
        w_vec = _weights_vec(w, cols)
        pnl = horizon_returns @ w_vec
        cutoff = np.percentile(pnl, (1.0 - float(confidence)) * 100.0)
        return Decimal(str(abs(float(cutoff))))

    flat = _var_for(weights)
    per_leg: dict[Leg, Decimal] = {
        "cbot": _var_for(_leg_weights(weights, "cbot")),
        "basis": _var_for(_leg_weights(weights, "basis")),
        "fx": _var_for(_leg_weights(weights, "fx")),
    }

    return VaRResult(
        method="monte_carlo",
        confidence=confidence,
        horizon_days=horizon_days,
        value_brl=flat,
        per_leg=per_leg,
        n_observations=len(returns),
        seed=rng_seed,
    )
