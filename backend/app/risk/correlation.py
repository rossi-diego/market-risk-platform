"""Empirical correlation + positive-semi-definite guards for risk simulation.

`np.linalg.cholesky` requires a strictly PSD matrix. Empirical correlation
computed from noisy samples occasionally has tiny negative eigenvalues from
numerical drift; `nearest_psd` floors them at `eps` so Cholesky succeeds.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def correlation_matrix(returns: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    """Empirical correlation matrix of the factor columns.

    Returns `(corr, names)` where `corr[i, j]` is the Pearson correlation
    between `names[i]` and `names[j]`.
    """
    if returns.empty:
        raise ValueError("returns DataFrame is empty")
    names = list(returns.columns)
    data = returns.to_numpy(dtype=float).T
    corr = np.corrcoef(data)
    # np.corrcoef collapses a single-row input to a scalar; wrap it.
    if corr.ndim == 0:
        corr = np.array([[1.0]])
    return corr, names


def nearest_psd(matrix: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    """Floor any eigenvalues below `eps` at `eps` and reconstruct a PSD matrix.

    The result is symmetrized with its transpose to wash out tiny asymmetries
    from the eigh/reconstruct roundtrip. Off-diagonal structure is preserved
    in proportion to the input.
    """
    sym = (matrix + matrix.T) / 2.0
    eigenvalues, eigenvectors = np.linalg.eigh(sym)
    clipped = np.clip(eigenvalues, eps, None)
    reconstructed = eigenvectors @ np.diag(clipped) @ eigenvectors.T
    result: np.ndarray = (reconstructed + reconstructed.T) / 2.0
    return result


def cholesky_factor(corr: np.ndarray) -> np.ndarray:
    """Lower-triangular `L` such that `L @ L.T ≈ corr`.

    Falls back to `nearest_psd(corr)` if the raw input isn't PSD enough for
    `np.linalg.cholesky`.
    """
    try:
        return np.linalg.cholesky(corr)
    except np.linalg.LinAlgError:
        return np.linalg.cholesky(nearest_psd(corr))
