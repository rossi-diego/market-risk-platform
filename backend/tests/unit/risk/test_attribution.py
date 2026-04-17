"""Unit tests for risk/attribution.py."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pandas as pd
import pytest

from app.risk.attribution import component_var, marginal_var
from app.risk.types import PositionWeight
from app.risk.var import parametric_var
from tests.fixtures.price_history import correlated_normal_returns


def _make_positions(n: int = 5) -> list[PositionWeight]:
    """5 positions each with a random-ish BRL weight across 3 factors."""
    base = [
        {"ZS=F": Decimal("1000"), "ZC=F": Decimal("0"), "USDBRL=X": Decimal("500")},
        {"ZS=F": Decimal("500"), "ZC=F": Decimal("500"), "USDBRL=X": Decimal("0")},
        {"ZS=F": Decimal("0"), "ZC=F": Decimal("1000"), "USDBRL=X": Decimal("500")},
        {"ZS=F": Decimal("750"), "ZC=F": Decimal("250"), "USDBRL=X": Decimal("750")},
        {"ZS=F": Decimal("-500"), "ZC=F": Decimal("500"), "USDBRL=X": Decimal("250")},
    ][:n]
    return [
        PositionWeight(
            position_id=uuid4(),
            label=f"position-{i}",
            weight_brl=sum(fe.values(), start=Decimal(0)),
            factor_exposures=fe,
        )
        for i, fe in enumerate(base)
    ]


def test_component_var_sums_to_flat() -> None:
    rets = correlated_normal_returns(n_days=1500, seed=42)
    positions = _make_positions()
    # Portfolio weights = sum of position exposures per factor
    portfolio_weights = {"ZS=F": Decimal(0), "ZC=F": Decimal(0), "USDBRL=X": Decimal(0)}
    for p in positions:
        for k, v in p.factor_exposures.items():
            portfolio_weights[k] += v

    flat = parametric_var(rets, portfolio_weights, Decimal("0.95"), 1)
    components = component_var(positions, rets, Decimal("0.95"), 1)
    component_sum = sum((c.contribution_brl for c in components), start=Decimal(0))
    # c_i sum should equal flat VaR exactly (parametric closed form).
    err = abs(float(component_sum) - float(flat.value_brl)) / float(flat.value_brl)
    assert err < 0.01


def test_component_var_ordering() -> None:
    rets = correlated_normal_returns(n_days=1000, seed=2)
    positions = _make_positions()
    components = component_var(positions, rets, Decimal("0.95"), 1)
    contributions = [c.contribution_brl for c in components]
    assert contributions == sorted(contributions, reverse=True)


def test_component_var_share_pct_sums_to_100() -> None:
    rets = correlated_normal_returns(n_days=1000, seed=5)
    positions = _make_positions()
    components = component_var(positions, rets, Decimal("0.95"), 1)
    total_share = sum((c.share_pct for c in components), start=Decimal(0))
    assert abs(float(total_share) - 100.0) < 0.001


def test_component_var_empty_positions() -> None:
    rets = correlated_normal_returns(n_days=500, seed=1)
    assert component_var([], rets) == []


def test_component_var_empty_returns_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        component_var(_make_positions(), pd.DataFrame())


def test_marginal_var_positive_shift_increases_var_for_long_book() -> None:
    """On a long-only positive-correlation book, enlarging any position raises VaR."""
    rets = correlated_normal_returns(n_days=1500, seed=11)
    # Build a 3-position *long-only* portfolio on the same factor
    long_positions = [
        PositionWeight(
            position_id=uuid4(),
            label=f"L{i}",
            weight_brl=Decimal("1000"),
            factor_exposures={"ZS=F": Decimal("1000")},
        )
        for i in range(3)
    ]
    delta = marginal_var(long_positions[0], long_positions, rets, Decimal("0.10"))
    assert delta > 0


def test_marginal_var_empty_portfolio() -> None:
    rets = correlated_normal_returns(n_days=100, seed=1)
    pos = _make_positions(1)[0]
    assert marginal_var(pos, [], rets) == Decimal(0)


def test_marginal_var_empty_returns_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        positions = _make_positions(1)
        marginal_var(positions[0], positions, pd.DataFrame())


def test_component_var_zero_portfolio() -> None:
    rets = correlated_normal_returns(n_days=500, seed=1)
    zero_positions = [
        PositionWeight(
            position_id=uuid4(),
            label="zero",
            weight_brl=Decimal(0),
            factor_exposures={"ZS=F": Decimal(0), "ZC=F": Decimal(0), "USDBRL=X": Decimal(0)},
        )
    ]
    components = component_var(zero_positions, rets)
    assert all(c.contribution_brl == Decimal(0) for c in components)
    assert all(c.share_pct == Decimal(0) for c in components)
