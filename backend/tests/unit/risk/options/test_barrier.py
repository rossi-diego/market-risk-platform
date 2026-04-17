"""Monte-Carlo barrier pricer unit tests."""

from __future__ import annotations

from decimal import Decimal

from app.risk.options.barrier import barrier_mc
from app.risk.options.bsm import bsm_price


def test_up_and_out_with_huge_barrier_approaches_vanilla() -> None:
    """If the barrier is so far away that it never hits, up-and-out ≈ vanilla."""
    S, K, T, r, sigma = (
        Decimal("100"),
        Decimal("100"),
        Decimal("1"),
        Decimal("0.05"),
        Decimal("0.2"),
    )
    vanilla = bsm_price(S, K, T, r, sigma, "call")
    uao = barrier_mc(
        S,
        K,
        T,
        r,
        sigma,
        "call",
        "up_and_out",
        barrier_level=Decimal("1000"),  # never hit
        rebate=Decimal("0"),
        n_paths=20_000,
        n_steps=100,
        seed=42,
    )
    # MC noise with N=20k around a price ≈ 10.45 → accept 5% tolerance
    assert abs(float(uao.price) - float(vanilla.price)) / float(vanilla.price) < 0.05


def test_in_out_parity() -> None:
    """up_and_in + up_and_out == vanilla (within MC noise)."""
    S, K, T, r, sigma = (
        Decimal("100"),
        Decimal("100"),
        Decimal("1"),
        Decimal("0.05"),
        Decimal("0.25"),
    )
    barrier = Decimal("120")
    vanilla = bsm_price(S, K, T, r, sigma, "call").price

    common = {
        "S": S,
        "K": K,
        "T": T,
        "r": r,
        "sigma": sigma,
        "option_type": "call",
        "barrier_level": barrier,
        "rebate": Decimal("0"),
        "n_paths": 30_000,
        "n_steps": 100,
        "seed": 42,
    }
    up_in = barrier_mc(**common, barrier_type="up_and_in").price  # type: ignore[arg-type]
    up_out = barrier_mc(**common, barrier_type="up_and_out").price  # type: ignore[arg-type]
    combined = float(up_in) + float(up_out)
    # MC noise ≤ 5% of vanilla
    assert abs(combined - float(vanilla)) / float(vanilla) < 0.05


def test_barrier_mc_reproducible_with_seed() -> None:
    args = {
        "S": Decimal("100"),
        "K": Decimal("100"),
        "T": Decimal("0.5"),
        "r": Decimal("0.05"),
        "sigma": Decimal("0.2"),
        "option_type": "call",
        "barrier_type": "up_and_out",
        "barrier_level": Decimal("120"),
        "rebate": Decimal("0"),
        "n_paths": 5_000,
        "n_steps": 50,
        "seed": 7,
    }
    a = barrier_mc(**args)  # type: ignore[arg-type]
    b = barrier_mc(**args)  # type: ignore[arg-type]
    assert a.price == b.price
    assert a.delta == b.delta


def test_down_and_out_put_basic() -> None:
    """Down-and-out put with barrier well below spot is close to vanilla."""
    S, K, T, r, sigma = (
        Decimal("100"),
        Decimal("100"),
        Decimal("1"),
        Decimal("0.05"),
        Decimal("0.2"),
    )
    vanilla = bsm_price(S, K, T, r, sigma, "put").price
    dao = barrier_mc(
        S,
        K,
        T,
        r,
        sigma,
        "put",
        "down_and_out",
        barrier_level=Decimal("10"),  # effectively never hit
        rebate=Decimal("0"),
        n_paths=20_000,
        n_steps=100,
        seed=42,
    )
    assert abs(float(dao.price) - float(vanilla)) / float(vanilla) < 0.05
