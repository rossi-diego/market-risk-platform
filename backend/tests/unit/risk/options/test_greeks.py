"""Unit tests for risk/options/greeks.py — unified option_delta dispatcher."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.models.enums import (
    BarrierType,
    CBOTInstrument,
    Commodity,
    FXInstrument,
    OptionType,
)
from app.risk.options.greeks import cbot_option_delta_brl_ton, option_delta


def test_option_delta_european_call_atm() -> None:
    delta = option_delta(
        instrument=CBOTInstrument.EUROPEAN_OPTION,
        spot=Decimal("100"),
        strike=Decimal("100"),
        years_to_maturity=Decimal("1"),
        option_type=OptionType.CALL,
    )
    assert 0.4 < float(delta) < 0.8


def test_option_delta_american_put() -> None:
    delta = option_delta(
        instrument=CBOTInstrument.AMERICAN_OPTION,
        spot=Decimal("100"),
        strike=Decimal("100"),
        years_to_maturity=Decimal("0.5"),
        option_type=OptionType.PUT,
    )
    assert -0.7 < float(delta) < -0.2


def test_option_delta_barrier_uao_call() -> None:
    delta = option_delta(
        instrument=CBOTInstrument.BARRIER_OPTION,
        spot=Decimal("100"),
        strike=Decimal("100"),
        years_to_maturity=Decimal("0.5"),
        option_type=OptionType.CALL,
        barrier_type=BarrierType.UP_AND_OUT,
        barrier_level=Decimal("150"),
        rebate=Decimal("0"),
        seed=42,
    )
    # Knock-out delta is smaller than vanilla call
    assert 0 < float(delta) < 0.6


def test_option_delta_barrier_requires_barrier_fields() -> None:
    with pytest.raises(ValueError, match="barrier options require"):
        option_delta(
            instrument=CBOTInstrument.BARRIER_OPTION,
            spot=Decimal("100"),
            strike=Decimal("100"),
            years_to_maturity=Decimal("0.5"),
            option_type=OptionType.CALL,
        )


def test_option_delta_rejects_non_option_instrument() -> None:
    with pytest.raises(ValueError, match="not an option"):
        option_delta(
            instrument=CBOTInstrument.FUTURE,
            spot=Decimal("100"),
            strike=Decimal("100"),
            years_to_maturity=Decimal("0.5"),
            option_type=None,
        )


def test_fx_european_option_delta() -> None:
    delta = option_delta(
        instrument=FXInstrument.EUROPEAN_OPTION,
        spot=Decimal("5.00"),
        strike=Decimal("5.00"),
        years_to_maturity=Decimal("0.25"),
        option_type=OptionType.CALL,
    )
    assert 0.4 < float(delta) < 0.7


def test_cbot_option_delta_brl_ton_scales_by_fx_and_bushels() -> None:
    brl_ton = cbot_option_delta_brl_ton(
        instrument=CBOTInstrument.EUROPEAN_OPTION,
        commodity=Commodity.SOJA,
        fx_brl_usd=Decimal("5"),
        spot_uscbu=Decimal("1000"),
        strike_uscbu=Decimal("1000"),
        years_to_maturity=Decimal("1"),
        option_type=OptionType.CALL,
    )
    # ATM call delta ~0.5 → 0.5 * 5 / 100 / 36.744 ≈ 0.00068 BRL/ton per 1 USc/bu
    assert 0.0003 < float(brl_ton) < 0.0012
