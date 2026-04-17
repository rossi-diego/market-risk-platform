"""Black-Scholes-Merton unit tests."""

from __future__ import annotations

import math
from decimal import Decimal

import pytest

from app.risk.options.bsm import bsm_price, implied_vol


def test_atm_call_textbook_value() -> None:
    """Hull Ch. 13 canonical example: S=K=100, T=1, r=0.05, σ=0.2."""
    res = bsm_price(
        Decimal("100"),
        Decimal("100"),
        Decimal("1"),
        Decimal("0.05"),
        Decimal("0.2"),
        "call",
    )
    assert abs(float(res.price) - 10.4506) < 1e-3
    assert abs(float(res.delta) - 0.6368) < 1e-3


def test_put_call_parity() -> None:
    """C + K·e^(-rT) == P + S·e^(-qT) for arbitrary inputs."""
    S = Decimal("95")
    K = Decimal("100")
    T = Decimal("0.5")
    r = Decimal("0.03")
    sigma = Decimal("0.25")
    q = Decimal("0")
    call = bsm_price(S, K, T, r, sigma, "call", q)
    put = bsm_price(S, K, T, r, sigma, "put", q)
    left = float(call.price) + float(K) * math.exp(-float(r) * float(T))
    right = float(put.price) + float(S) * math.exp(-float(q) * float(T))
    assert abs(left - right) < 1e-6


def test_atm_delta_is_near_half() -> None:
    call = bsm_price(
        Decimal("100"), Decimal("100"), Decimal("1"), Decimal("0"), Decimal("0.2"), "call"
    )
    put = bsm_price(
        Decimal("100"), Decimal("100"), Decimal("1"), Decimal("0"), Decimal("0.2"), "put"
    )
    assert abs(float(call.delta) - 0.5) < 0.05
    assert abs(float(put.delta) + 0.5) < 0.05


def test_implied_vol_roundtrip() -> None:
    S, K, T, r = Decimal("100"), Decimal("105"), Decimal("0.5"), Decimal("0.04")
    sigma_true = Decimal("0.3")
    market = bsm_price(S, K, T, r, sigma_true, "call").price
    iv = implied_vol(S, K, T, r, market, "call")
    # Round-trip: re-price with iv and compare
    re_priced = bsm_price(S, K, T, r, iv, "call").price
    assert abs(float(re_priced) - float(market)) < 1e-4


def test_implied_vol_raises_on_no_root() -> None:
    with pytest.raises(ValueError):
        # Price way below intrinsic — no valid IV in [0.001, 5]
        implied_vol(
            Decimal("100"), Decimal("100"), Decimal("1"), Decimal("0.05"), Decimal("-5"), "call"
        )


def test_call_price_monotonic_in_vol() -> None:
    prices = [
        float(
            bsm_price(
                Decimal("100"),
                Decimal("100"),
                Decimal("1"),
                Decimal("0.05"),
                Decimal(str(v)),
                "call",
            ).price
        )
        for v in (0.1, 0.2, 0.3, 0.4)
    ]
    assert prices == sorted(prices)


def test_gamma_is_positive_for_both() -> None:
    call = bsm_price(
        Decimal("100"), Decimal("100"), Decimal("1"), Decimal("0.05"), Decimal("0.2"), "call"
    )
    put = bsm_price(
        Decimal("100"), Decimal("100"), Decimal("1"), Decimal("0.05"), Decimal("0.2"), "put"
    )
    assert call.gamma > 0
    assert put.gamma > 0


def test_invalid_inputs_raise() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        bsm_price(
            Decimal("100"),
            Decimal("100"),
            Decimal("0"),
            Decimal("0.05"),
            Decimal("0.2"),
            "call",
        )
