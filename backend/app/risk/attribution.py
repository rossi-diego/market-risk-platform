"""Component VaR + marginal VaR.

Parametric attribution: for a portfolio of positions each with signed BRL
weight per factor, the component VaR of position `i` is

    c_i = (w_i · Σ · w_p) / σ_p  ×  z_α × sqrt(h)

which collapses to `c_i = w_i_factor_exposure ⋅ Σ ⋅ w_portfolio / σ_p` scaled
by the horizon-adjusted z-score. Property: `Σ c_i == flat_VaR` exactly (up to
floating-point), so `share_pct` values sum to 100.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

import numpy as np
import pandas as pd
from scipy.stats import norm

from app.risk.types import PositionContribution, PositionWeight


def _aggregate_weights(positions: list[PositionWeight], factor_names: list[str]) -> np.ndarray:
    agg = np.zeros(len(factor_names), dtype=float)
    for i, name in enumerate(factor_names):
        total = Decimal(0)
        for p in positions:
            total += p.factor_exposures.get(name, Decimal(0))
        agg[i] = float(total)
    return agg


def _position_weight_vec(position: PositionWeight, factor_names: list[str]) -> np.ndarray:
    return np.array(
        [float(position.factor_exposures.get(name, Decimal(0))) for name in factor_names],
        dtype=float,
    )


def component_var(
    positions: list[PositionWeight],
    returns: pd.DataFrame,
    confidence: Decimal = Decimal("0.95"),
    horizon_days: int = 1,
    method: Literal["parametric"] = "parametric",
) -> list[PositionContribution]:
    """Decompose flat VaR into position contributions (parametric method).

    Component VaR uses marginal contribution `MC_i = (Σ w)_i / σ_p`, so the
    position contribution is `c_i = w_i · MC_i × z × sqrt(h)`. Summing over
    positions recovers the flat VaR exactly.
    """
    if returns.empty:
        raise ValueError("returns DataFrame is empty")
    if not positions:
        return []

    factor_names = list(returns.columns)
    cov = returns.cov().to_numpy()
    z = float(norm.ppf(float(confidence)))
    sqrt_h = float(np.sqrt(horizon_days))

    w_portfolio = _aggregate_weights(positions, factor_names)
    portfolio_variance = float(w_portfolio @ cov @ w_portfolio)
    sigma_p = float(np.sqrt(max(portfolio_variance, 0.0)))

    if sigma_p == 0.0:
        # All-zero portfolio: every contribution is zero.
        return [
            PositionContribution(
                position_id=p.position_id,
                label=p.label,
                contribution_brl=Decimal(0),
                share_pct=Decimal(0),
            )
            for p in positions
        ]

    # marginal_vec[i] = d sigma_p / d w_i = (Σ w)_i / sigma_p
    marginal_vec = (cov @ w_portfolio) / sigma_p
    scale = z * sqrt_h

    contributions: list[PositionContribution] = []
    total_contribution = Decimal(0)
    for pos in positions:
        w_vec = _position_weight_vec(pos, factor_names)
        c_i_float = float(w_vec @ marginal_vec) * scale
        c_i = Decimal(str(c_i_float))
        total_contribution += c_i
        contributions.append(
            PositionContribution(
                position_id=pos.position_id,
                label=pos.label,
                contribution_brl=c_i,
                share_pct=Decimal(0),  # patched below
            )
        )

    # share_pct: position contribution / flat VaR. Use absolute contributions
    # for percentages so shorts that actually reduce risk show a negative share.
    flat_var_abs = abs(total_contribution)
    finalized: list[PositionContribution] = []
    for c in contributions:
        share = (
            Decimal(0)
            if flat_var_abs == 0
            else (c.contribution_brl / total_contribution) * Decimal(100)
        )
        finalized.append(
            PositionContribution(
                position_id=c.position_id,
                label=c.label,
                contribution_brl=c.contribution_brl,
                share_pct=share,
            )
        )

    finalized.sort(key=lambda x: x.contribution_brl, reverse=True)
    return finalized


def marginal_var(
    position: PositionWeight,
    portfolio: list[PositionWeight],
    returns: pd.DataFrame,
    shift_pct: Decimal = Decimal("0.01"),
    confidence: Decimal = Decimal("0.95"),
) -> Decimal:
    """BRL change in flat VaR when `position.weight_brl` is scaled by `shift_pct`."""
    if returns.empty:
        raise ValueError("returns DataFrame is empty")
    if not portfolio:
        return Decimal(0)

    factor_names = list(returns.columns)
    cov = returns.cov().to_numpy()
    z = float(norm.ppf(float(confidence)))

    def _flat_var(positions: list[PositionWeight]) -> float:
        w = _aggregate_weights(positions, factor_names)
        variance = float(w @ cov @ w)
        return abs(z * float(np.sqrt(max(variance, 0.0))))

    base = _flat_var(portfolio)

    shift_factor = Decimal(1) + shift_pct
    shifted_position = PositionWeight(
        position_id=position.position_id,
        label=position.label,
        weight_brl=position.weight_brl * shift_factor,
        factor_exposures={k: v * shift_factor for k, v in position.factor_exposures.items()},
    )
    shifted_portfolio = [
        shifted_position if p.position_id == position.position_id else p for p in portfolio
    ]
    shifted = _flat_var(shifted_portfolio)
    return Decimal(str(shifted - base))
