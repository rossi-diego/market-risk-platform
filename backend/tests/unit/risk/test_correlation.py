"""Unit tests for risk/correlation.py."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.risk.correlation import cholesky_factor, correlation_matrix, nearest_psd


def test_correlation_matrix_perfectly_correlated() -> None:
    rng = np.random.default_rng(42)
    x = rng.normal(size=500)
    df = pd.DataFrame({"a": x, "b": x})  # perfectly correlated
    corr, names = correlation_matrix(df)
    assert names == ["a", "b"]
    assert corr.shape == (2, 2)
    assert abs(corr[0, 1] - 1.0) < 1e-9


def test_correlation_matrix_orthogonal() -> None:
    rng = np.random.default_rng(7)
    df = pd.DataFrame(
        {
            "a": rng.normal(size=5000),
            "b": rng.normal(size=5000),
        }
    )
    corr, _ = correlation_matrix(df)
    # Two independent series: |ρ| should be near 0 on 5000 samples.
    assert abs(corr[0, 1]) < 0.05


def test_correlation_matrix_diagonal_is_one() -> None:
    rng = np.random.default_rng(1)
    df = pd.DataFrame(rng.normal(size=(1000, 5)), columns=list("abcde"))
    corr, _ = correlation_matrix(df)
    assert np.allclose(np.diag(corr), 1.0)


def test_correlation_matrix_empty_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        correlation_matrix(pd.DataFrame())


def test_nearest_psd_fixes_tiny_negative_eigenvalue() -> None:
    # Build a 3x3 matrix with one slightly negative eigenvalue.
    base = np.eye(3)
    q, _ = np.linalg.qr(np.random.default_rng(3).normal(size=(3, 3)))
    evals = np.array([1.0, 0.5, -1e-10])
    bad = q @ np.diag(evals) @ q.T
    fixed = nearest_psd(bad)
    eigs = np.linalg.eigvalsh(fixed)
    assert (eigs >= -1e-12).all()
    # Result is symmetric within tolerance
    assert np.allclose(fixed, fixed.T)
    # Shape preserved
    assert fixed.shape == base.shape


def test_cholesky_roundtrip_on_psd_matrix() -> None:
    a = np.array(
        [
            [1.0, 0.5, 0.2],
            [0.5, 1.0, 0.3],
            [0.2, 0.3, 1.0],
        ]
    )
    L = cholesky_factor(a)
    reconstructed = L @ L.T
    assert np.allclose(reconstructed, a, atol=1e-10)


def test_cholesky_falls_back_to_nearest_psd() -> None:
    # Non-PSD (one negative eigenvalue) — the fallback must still produce L.
    q, _ = np.linalg.qr(np.random.default_rng(9).normal(size=(3, 3)))
    evals = np.array([1.0, 0.2, -0.01])
    bad = q @ np.diag(evals) @ q.T
    # Symmetrize so we start with a valid symmetric candidate.
    bad = (bad + bad.T) / 2
    L = cholesky_factor(bad)
    assert L.shape == (3, 3)
