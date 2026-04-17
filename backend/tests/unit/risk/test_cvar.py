"""Unit tests for Expected Shortfall (CVaR)."""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import pytest
from scipy.stats import norm

from app.risk.cvar import expected_shortfall
from app.risk.var import historical_var, monte_carlo_var, parametric_var
from tests.fixtures.price_history import iid_normal_returns

_WEIGHTS = {
    "ZS=F": Decimal("1000"),
    "ZC=F": Decimal("1000"),
    "USDBRL=X": Decimal("1000"),
}


@pytest.mark.parametrize(
    ("method", "confidence"),
    [
        ("historical", Decimal("0.95")),
        ("historical", Decimal("0.975")),
        ("parametric", Decimal("0.95")),
        ("parametric", Decimal("0.975")),
        ("monte_carlo", Decimal("0.95")),
    ],
)
def test_cvar_geq_var_same_confidence(method: str, confidence: Decimal) -> None:
    rets = iid_normal_returns(n_days=2000, sigma=0.01, seed=42)
    cvar = expected_shortfall(rets, _WEIGHTS, confidence, 1, method=method, seed=42)  # type: ignore[arg-type]
    if method == "historical":
        var = historical_var(rets, _WEIGHTS, confidence, 1)
    elif method == "parametric":
        var = parametric_var(rets, _WEIGHTS, confidence, 1)
    else:
        var = monte_carlo_var(rets, _WEIGHTS, confidence, 1, n_paths=10_000, seed=42)
    assert cvar.value_brl >= var.value_brl - Decimal("0.01")


def test_cvar_parametric_closed_form() -> None:
    """For normal data: ES = φ(z) / (1-α) × σ_p."""
    rets = iid_normal_returns(n_days=2000, sigma=0.01, seed=42)
    cvar = expected_shortfall(rets, _WEIGHTS, Decimal("0.975"), 1, method="parametric")

    w = np.array([1000.0, 1000.0, 1000.0])
    cov = rets.cov().to_numpy()
    sigma_p = float(np.sqrt(w @ cov @ w))
    alpha = 0.975
    z = float(norm.ppf(alpha))
    expected = norm.pdf(z) / (1 - alpha) * sigma_p

    assert abs(float(cvar.value_brl) - expected) / expected < 0.001


def test_cvar_reproducible_mc() -> None:
    rets = iid_normal_returns(n_days=500, sigma=0.01, seed=1)
    a = expected_shortfall(rets, _WEIGHTS, Decimal("0.975"), 1, method="monte_carlo", seed=7)
    b = expected_shortfall(rets, _WEIGHTS, Decimal("0.975"), 1, method="monte_carlo", seed=7)
    assert a.value_brl == b.value_brl


def test_cvar_empty_raises() -> None:
    import pandas as pd

    with pytest.raises(ValueError, match="empty"):
        expected_shortfall(pd.DataFrame(), _WEIGHTS, Decimal("0.975"), 1, method="historical")
