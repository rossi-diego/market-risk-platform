"""Unit tests for risk/mc.py — correlated paths + fan chart."""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from app.risk.mc import fan_chart_paths, simulate_correlated_paths
from tests.fixtures.price_history import correlated_normal_returns


def test_simulate_paths_shape() -> None:
    corr = np.eye(3)
    paths = simulate_correlated_paths(
        mu=np.zeros(3),
        sigma=np.array([0.01, 0.01, 0.02]),
        corr=corr,
        n_paths=500,
        n_steps=10,
        dt=1.0,
        seed=42,
    )
    assert paths.shape == (500, 10, 3)


def test_mc_reproducibility_bit_exact() -> None:
    kwargs = {
        "mu": np.zeros(3),
        "sigma": np.array([0.01, 0.01, 0.02]),
        "corr": np.eye(3),
        "n_paths": 200,
        "n_steps": 5,
        "dt": 1.0,
        "seed": 42,
    }
    a = simulate_correlated_paths(**kwargs)
    b = simulate_correlated_paths(**kwargs)
    assert np.array_equal(a, b)


def test_correlated_paths_preserve_correlation() -> None:
    true_corr = np.array(
        [
            [1.0, 0.6, 0.2],
            [0.6, 1.0, 0.1],
            [0.2, 0.1, 1.0],
        ]
    )
    paths = simulate_correlated_paths(
        mu=np.zeros(3),
        sigma=np.array([1.0, 1.0, 1.0]),
        corr=true_corr,
        n_paths=50_000,
        n_steps=1,
        dt=1.0,
        seed=7,
    )
    # shape (50k, 1, 3) → take t=0 slice
    shocks = paths[:, 0, :]
    # Empirical correlation of the cumulative (single-step) log prices
    empirical = np.corrcoef(shocks.T)
    assert np.allclose(empirical, true_corr, atol=0.05)


def test_fan_chart_percentiles_monotone() -> None:
    rets = correlated_normal_returns(n_days=1000, seed=1)
    weights = {
        "ZS=F": Decimal("1000"),
        "ZC=F": Decimal("1000"),
        "USDBRL=X": Decimal("1000"),
    }
    fan = fan_chart_paths(weights, rets, horizon_days=10, n_paths=2000, seed=42)
    for day in range(fan.horizon_days):
        p5 = fan.percentiles[5][day]
        p25 = fan.percentiles[25][day]
        p50 = fan.percentiles[50][day]
        p75 = fan.percentiles[75][day]
        p95 = fan.percentiles[95][day]
        assert p5 <= p25 <= p50 <= p75 <= p95


def test_fan_chart_reproducibility() -> None:
    rets = correlated_normal_returns(n_days=500, seed=3)
    weights = {
        "ZS=F": Decimal("1000"),
        "ZC=F": Decimal("1000"),
        "USDBRL=X": Decimal("1000"),
    }
    a = fan_chart_paths(weights, rets, horizon_days=5, n_paths=1000, seed=99)
    b = fan_chart_paths(weights, rets, horizon_days=5, n_paths=1000, seed=99)
    for q in (5, 25, 50, 75, 95):
        assert a.percentiles[q] == b.percentiles[q]


def test_fan_chart_empty_returns_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        fan_chart_paths({"ZS=F": Decimal("1")}, pd.DataFrame(), horizon_days=1, n_paths=100)


def test_simulate_paths_shape_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="sigma shape"):
        simulate_correlated_paths(
            mu=np.zeros(3),
            sigma=np.array([0.01, 0.01]),  # wrong length
            corr=np.eye(3),
            n_paths=10,
            n_steps=1,
            dt=1.0,
            seed=1,
        )
    with pytest.raises(ValueError, match="corr shape"):
        simulate_correlated_paths(
            mu=np.zeros(3),
            sigma=np.array([0.01, 0.01, 0.01]),
            corr=np.eye(4),  # wrong shape
            n_paths=10,
            n_steps=1,
            dt=1.0,
            seed=1,
        )
