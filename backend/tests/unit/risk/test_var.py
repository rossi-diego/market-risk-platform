"""Unit tests for the 3 VaR methods."""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import pytest

from app.risk.var import historical_var, monte_carlo_var, parametric_var
from tests.fixtures.price_history import (
    correlated_normal_returns,
    iid_normal_returns,
)

# A BRL-exposure-per-factor weight map. Equal weight across 3 factors.
_WEIGHTS = {
    "ZS=F": Decimal("1000"),
    "ZC=F": Decimal("1000"),
    "USDBRL=X": Decimal("1000"),
}


def test_parametric_flat_matches_formula() -> None:
    rets = iid_normal_returns(n_days=2000, sigma=0.01, seed=42)
    r = parametric_var(rets, _WEIGHTS, Decimal("0.95"), 1)
    # w' Σ w for equal weights + IID N(0, 0.01^2) cov ≈ 3 * 1000^2 * 0.0001 = 300
    # sigma_p ≈ sqrt(300) ≈ 17.32; z_0.95 ≈ 1.6449; expected ≈ 28.49
    w = np.array([1000.0, 1000.0, 1000.0])
    cov = rets.cov().to_numpy()
    sigma_p = float(np.sqrt(w @ cov @ w))
    expected = 1.6449 * sigma_p
    assert abs(float(r.value_brl) - expected) / expected < 0.01


def test_historical_approximates_parametric_on_normal() -> None:
    rets = iid_normal_returns(n_days=2000, sigma=0.01, seed=7)
    hist = historical_var(rets, _WEIGHTS, Decimal("0.95"), 1, window=1000)
    param = parametric_var(rets, _WEIGHTS, Decimal("0.95"), 1)
    # On normal data the two should be within ~10%.
    ratio = float(hist.value_brl) / float(param.value_brl)
    assert 0.85 < ratio < 1.15, f"historical/parametric ratio {ratio:.3f} out of band"


def test_mc_reproducible_with_seed() -> None:
    rets = iid_normal_returns(n_days=500, sigma=0.01, seed=1)
    a = monte_carlo_var(rets, _WEIGHTS, Decimal("0.95"), 1, n_paths=5_000, seed=42)
    b = monte_carlo_var(rets, _WEIGHTS, Decimal("0.95"), 1, n_paths=5_000, seed=42)
    assert a.value_brl == b.value_brl


def test_mc_different_seeds_give_different_results() -> None:
    rets = iid_normal_returns(n_days=500, sigma=0.01, seed=1)
    a = monte_carlo_var(rets, _WEIGHTS, Decimal("0.95"), 1, n_paths=5_000, seed=1)
    b = monte_carlo_var(rets, _WEIGHTS, Decimal("0.95"), 1, n_paths=5_000, seed=2)
    assert a.value_brl != b.value_brl


def test_per_leg_sums_geq_flat() -> None:
    rets = correlated_normal_returns(n_days=1000, seed=42)
    r = parametric_var(rets, _WEIGHTS, Decimal("0.95"), 1)
    sum_legs = sum(r.per_leg.values())
    # Flat <= sum per leg (diversification) — with positive correlation it can be close.
    assert sum_legs >= r.value_brl - Decimal("0.001")


def test_sqrt_h_scaling_parametric() -> None:
    rets = iid_normal_returns(n_days=2000, sigma=0.01, seed=13)
    r1 = parametric_var(rets, _WEIGHTS, Decimal("0.95"), 1)
    r10 = parametric_var(rets, _WEIGHTS, Decimal("0.95"), 10)
    ratio = float(r10.value_brl) / float(r1.value_brl)
    expected = float(np.sqrt(10))
    assert abs(ratio - expected) / expected < 0.01


def test_confidence_monotonic_parametric() -> None:
    rets = iid_normal_returns(n_days=1000, seed=3)
    r95 = parametric_var(rets, _WEIGHTS, Decimal("0.95"), 1)
    r99 = parametric_var(rets, _WEIGHTS, Decimal("0.99"), 1)
    assert r99.value_brl > r95.value_brl


def test_confidence_monotonic_historical() -> None:
    rets = iid_normal_returns(n_days=2000, sigma=0.01, seed=5)
    r95 = historical_var(rets, _WEIGHTS, Decimal("0.95"), 1)
    r99 = historical_var(rets, _WEIGHTS, Decimal("0.99"), 1)
    assert r99.value_brl >= r95.value_brl


def test_var_nonnegative() -> None:
    rets = iid_normal_returns(n_days=500, seed=2)
    for fn in (historical_var, parametric_var):
        r = fn(rets, _WEIGHTS, Decimal("0.95"), 1)
        assert r.value_brl >= 0


def test_doubling_weights_doubles_var_parametric() -> None:
    rets = iid_normal_returns(n_days=1000, seed=4)
    doubled = {k: v * 2 for k, v in _WEIGHTS.items()}
    r1 = parametric_var(rets, _WEIGHTS, Decimal("0.95"), 1)
    r2 = parametric_var(rets, doubled, Decimal("0.95"), 1)
    ratio = float(r2.value_brl) / float(r1.value_brl)
    assert abs(ratio - 2.0) < 0.001


def test_empty_returns_raises() -> None:
    import pandas as pd

    with pytest.raises(ValueError, match="empty"):
        parametric_var(pd.DataFrame(), _WEIGHTS, Decimal("0.95"), 1)
