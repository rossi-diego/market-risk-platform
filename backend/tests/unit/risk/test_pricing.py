"""Unit tests for risk/pricing.py.

Ground truth is computed by hand in CLAUDE.md > Price Formation Model.
All inputs/outputs are Decimal; float is banned in the risk engine.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.models.enums import Commodity
from app.risk.pricing import (
    TONS_TO_BUSHELS,
    basis_delta_brl_ton,
    cbot_delta_brl_ton,
    fx_delta_brl_ton,
    mtm_value_brl,
    price_brl_ton,
)

TOL = Decimal("0.0001")


def _approx_eq(a: Decimal, b: Decimal, tol: Decimal = TOL) -> bool:
    return abs(a - b) <= tol


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_tons_to_bushels_has_exactly_two_commodities() -> None:
    assert set(TONS_TO_BUSHELS.keys()) == {Commodity.SOJA, Commodity.MILHO}
    assert TONS_TO_BUSHELS[Commodity.SOJA] == Decimal("36.744")
    assert TONS_TO_BUSHELS[Commodity.MILHO] == Decimal("56.0")


# ---------------------------------------------------------------------------
# price_brl_ton
# ---------------------------------------------------------------------------


def test_price_brl_ton_soja_canonical() -> None:
    # (1000/100/36.744)*5 + 0.5*5/36.744 = 50/36.744 + 2.5/36.744 ≈ 1.42880...
    # Spec gives the rounded display value 1.4287; the exact value is 1.4288.
    # Both live inside the 4-decimal tolerance band used downstream.
    got = price_brl_ton(Commodity.SOJA, Decimal("1000"), Decimal("5"), Decimal("0.5"))
    expected = Decimal("1000") / Decimal("100") / Decimal("36.744") * Decimal("5") + Decimal(
        "0.5"
    ) * Decimal("5") / Decimal("36.744")
    assert got == expected
    assert _approx_eq(got, Decimal("1.4288"))


def test_price_brl_ton_milho_canonical() -> None:
    # (400/100/56)*5 + 0.3*5/56 = 20/56 + 1.5/56 ≈ 0.38392...
    got = price_brl_ton(Commodity.MILHO, Decimal("400"), Decimal("5"), Decimal("0.3"))
    expected = Decimal("400") / Decimal("100") / Decimal("56.0") * Decimal("5") + Decimal(
        "0.3"
    ) * Decimal("5") / Decimal("56.0")
    assert got == expected
    assert _approx_eq(got, Decimal("0.3839"))


def test_price_brl_ton_zero_premium() -> None:
    # pure CBOT component, no basis
    got = price_brl_ton(Commodity.SOJA, Decimal("1000"), Decimal("5"), Decimal("0"))
    expected = (Decimal("1000") / Decimal("100") / Decimal("36.744")) * Decimal("5")
    assert got == expected


def test_price_brl_ton_zero_cbot() -> None:
    # pure basis component, no CBOT
    got = price_brl_ton(Commodity.SOJA, Decimal("0"), Decimal("5"), Decimal("0.5"))
    expected = Decimal("0.5") * Decimal("5") / Decimal("36.744")
    assert got == expected


# ---------------------------------------------------------------------------
# mtm_value_brl — total * price
# ---------------------------------------------------------------------------


def test_mtm_value_brl_scales_linearly() -> None:
    p = price_brl_ton(Commodity.SOJA, Decimal("1000"), Decimal("5"), Decimal("0.5"))
    mtm = mtm_value_brl(
        Commodity.SOJA,
        Decimal("250"),
        Decimal("1000"),
        Decimal("5"),
        Decimal("0.5"),
    )
    assert mtm == p * Decimal("250")


# ---------------------------------------------------------------------------
# Sensitivities
# ---------------------------------------------------------------------------


def test_cbot_delta_soja() -> None:
    # 5 / 100 / 36.744 ≈ 0.0013608
    got = cbot_delta_brl_ton(Commodity.SOJA, Decimal("5"))
    assert _approx_eq(got, Decimal("0.001361"), Decimal("0.000001"))


def test_cbot_delta_milho() -> None:
    got = cbot_delta_brl_ton(Commodity.MILHO, Decimal("5"))
    expected = Decimal("5") / Decimal("100") / Decimal("56.0")
    assert got == expected


def test_fx_delta_soja_canonical() -> None:
    # ((1000/100/36.744) + 0.5/36.744) * 0.01 ≈ (0.272132 + 0.013608) * 0.01 ≈ 0.002857
    got = fx_delta_brl_ton(Commodity.SOJA, Decimal("1000"), Decimal("0.5"))
    assert _approx_eq(got, Decimal("0.002857"), Decimal("0.000001"))


def test_basis_delta_soja() -> None:
    # 5 / 36.744 ≈ 0.136076
    got = basis_delta_brl_ton(Commodity.SOJA, Decimal("5"))
    assert _approx_eq(got, Decimal("0.136076"), Decimal("0.000001"))


def test_basis_delta_milho() -> None:
    got = basis_delta_brl_ton(Commodity.MILHO, Decimal("5"))
    expected = Decimal("5") / Decimal("56.0")
    assert got == expected


# ---------------------------------------------------------------------------
# Symmetry: finite-difference must match analytical CBOT delta at linearity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("commodity", [Commodity.SOJA, Commodity.MILHO])
def test_cbot_delta_matches_finite_difference(commodity: Commodity) -> None:
    cbot = Decimal("1000") if commodity == Commodity.SOJA else Decimal("400")
    fx = Decimal("5")
    premium = Decimal("0.5")
    step = Decimal("10")  # 10 USc/bu shock

    p0 = price_brl_ton(commodity, cbot, fx, premium)
    p1 = price_brl_ton(commodity, cbot + step, fx, premium)
    analytical = cbot_delta_brl_ton(commodity, fx) * step
    assert _approx_eq(p1 - p0, analytical, Decimal("0.000001"))


@pytest.mark.parametrize("commodity", [Commodity.SOJA, Commodity.MILHO])
def test_basis_delta_matches_finite_difference(commodity: Commodity) -> None:
    cbot = Decimal("1000")
    fx = Decimal("5")
    premium = Decimal("0.5")
    step = Decimal("0.10")

    p0 = price_brl_ton(commodity, cbot, fx, premium)
    p1 = price_brl_ton(commodity, cbot, fx, premium + step)
    analytical = basis_delta_brl_ton(commodity, fx) * step
    assert _approx_eq(p1 - p0, analytical, Decimal("0.000001"))


@pytest.mark.parametrize("commodity", [Commodity.SOJA, Commodity.MILHO])
def test_fx_delta_matches_finite_difference(commodity: Commodity) -> None:
    cbot = Decimal("1000") if commodity == Commodity.SOJA else Decimal("400")
    fx = Decimal("5")
    premium = Decimal("0.5")
    step = Decimal("0.01")  # one FX tick

    p0 = price_brl_ton(commodity, cbot, fx, premium)
    p1 = price_brl_ton(commodity, cbot, fx + step, premium)
    analytical = fx_delta_brl_ton(commodity, cbot, premium)
    assert _approx_eq(p1 - p0, analytical, Decimal("0.000001"))
