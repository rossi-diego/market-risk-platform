"""Synthetic return-series fixtures for the risk-engine tests.

All generators are seed-deterministic.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

_DEFAULT_FACTORS = ("ZS=F", "ZC=F", "USDBRL=X")


def iid_normal_returns(
    *,
    n_days: int = 1000,
    sigma: float = 0.01,
    factors: tuple[str, ...] = _DEFAULT_FACTORS,
    seed: int = 42,
) -> pd.DataFrame:
    """N(0, sigma) IID returns, identical distribution per factor."""
    rng = np.random.default_rng(seed)
    data = rng.normal(loc=0.0, scale=sigma, size=(n_days, len(factors)))
    index = pd.date_range(end="2026-04-15", periods=n_days, freq="B")
    return pd.DataFrame(data, index=index, columns=list(factors))


def correlated_normal_returns(
    *,
    n_days: int = 1000,
    cov: np.ndarray | None = None,
    factors: tuple[str, ...] = _DEFAULT_FACTORS,
    seed: int = 42,
) -> pd.DataFrame:
    """Multivariate normal returns with a user-specified covariance matrix."""
    if cov is None:
        base = np.array(
            [
                [0.0001, 0.00005, 0.00002],
                [0.00005, 0.0001, 0.00001],
                [0.00002, 0.00001, 0.0002],
            ]
        )
        cov = base
    rng = np.random.default_rng(seed)
    data = rng.multivariate_normal(mean=np.zeros(len(factors)), cov=cov, size=n_days)
    index = pd.date_range(end="2026-04-15", periods=n_days, freq="B")
    return pd.DataFrame(data, index=index, columns=list(factors))
