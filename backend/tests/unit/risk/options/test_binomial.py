"""CRR binomial pricer unit tests."""

from __future__ import annotations

from decimal import Decimal

from app.risk.options.binomial import crr_american
from app.risk.options.bsm import bsm_price


def test_european_like_binomial_matches_bsm() -> None:
    """With no dividends, an American call equals European (Merton) ⇒ CRR ≈ BSM."""
    S = Decimal("100")
    K = Decimal("100")
    T = Decimal("1")
    r = Decimal("0.05")
    sigma = Decimal("0.2")
    bsm = bsm_price(S, K, T, r, sigma, "call")
    crr = crr_american(S, K, T, r, sigma, "call", n_steps=800)
    assert abs(float(crr.price) - float(bsm.price)) < 5e-3


def test_american_put_at_least_european() -> None:
    """American put ≥ European put (early exercise never hurts)."""
    S, K, T, r, sigma = (
        Decimal("100"),
        Decimal("100"),
        Decimal("1"),
        Decimal("0.05"),
        Decimal("0.25"),
    )
    q = Decimal("0.04")
    european = bsm_price(S, K, T, r, sigma, "put", q)
    american = crr_american(S, K, T, r, sigma, "put", q, n_steps=500)
    assert float(american.price) >= float(european.price) - 1e-4


def test_deep_itm_call_delta_near_one() -> None:
    res = crr_american(
        Decimal("150"),
        Decimal("100"),
        Decimal("1"),
        Decimal("0.05"),
        Decimal("0.2"),
        "call",
        n_steps=200,
    )
    assert float(res.delta) > 0.9


def test_deep_itm_put_delta_near_minus_one() -> None:
    res = crr_american(
        Decimal("50"),
        Decimal("100"),
        Decimal("1"),
        Decimal("0.05"),
        Decimal("0.2"),
        "put",
        n_steps=200,
    )
    assert float(res.delta) < -0.9


def test_binomial_price_positive() -> None:
    res = crr_american(
        Decimal("100"),
        Decimal("110"),
        Decimal("0.5"),
        Decimal("0.05"),
        Decimal("0.25"),
        "call",
        n_steps=200,
    )
    assert res.price > 0
    assert res.gamma >= 0
