"""Unit tests for risk/exposure.py."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.models.basis import BasisForward
from app.models.cbot import CBOTDerivative
from app.models.enums import (
    CBOTInstrument,
    Commodity,
    FixationMode,
    FXInstrument,
    OptionType,
    Side,
)
from app.models.fx import FXDerivative
from app.models.physical import PhysicalFixation, PhysicalFrame
from app.risk.exposure import aggregate_exposure, open_exposure_frame
from app.risk.types import DomainError, LegExposure

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _frame(qty: str, commodity: Commodity = Commodity.SOJA, side: Side = Side.BUY) -> PhysicalFrame:
    return PhysicalFrame(
        id=uuid4(),
        user_id=uuid4(),
        commodity=commodity,
        side=side,
        quantity_tons=Decimal(qty),
        delivery_start=date(2026, 5, 1),
        delivery_end=date(2026, 7, 31),
        status="open",
    )


def _fix(
    frame_id: UUID,
    mode: FixationMode,
    qty: str,
    cbot: str | None = None,
    basis: str | None = None,
    fxv: str | None = None,
) -> PhysicalFixation:
    return PhysicalFixation(
        id=uuid4(),
        frame_id=frame_id,
        fixation_mode=mode,
        quantity_tons=Decimal(qty),
        fixation_date=date(2026, 4, 15),
        cbot_fixed=Decimal(cbot) if cbot is not None else None,
        basis_fixed=Decimal(basis) if basis is not None else None,
        fx_fixed=Decimal(fxv) if fxv is not None else None,
    )


# ---------------------------------------------------------------------------
# LegExposure invariant
# ---------------------------------------------------------------------------


def test_leg_exposure_rejects_negative() -> None:
    with pytest.raises(ValueError):
        LegExposure(
            cbot_qty_tons=Decimal("-1"),
            basis_qty_tons=Decimal(0),
            fx_qty_tons=Decimal(0),
        )


# ---------------------------------------------------------------------------
# open_exposure_frame — all 5 fixation modes
# ---------------------------------------------------------------------------


def test_frame_with_no_fixations_is_fully_open() -> None:
    f = _frame("1000")
    fe = open_exposure_frame(f, [])
    assert fe.open.cbot_qty_tons == Decimal("1000")
    assert fe.open.basis_qty_tons == Decimal("1000")
    assert fe.open.fx_qty_tons == Decimal("1000")
    assert fe.locked.cbot_qty_tons == Decimal(0)
    assert fe.locked.basis_qty_tons == Decimal(0)
    assert fe.locked.fx_qty_tons == Decimal(0)
    assert fe.total_tons == Decimal("1000")
    assert fe.side == Side.BUY


def test_frame_with_flat_fixation_locks_all_three_legs() -> None:
    f = _frame("1000")
    fx = _fix(f.id, FixationMode.FLAT, "300", cbot="1420", basis="0.5", fxv="5.00")
    fe = open_exposure_frame(f, [fx])
    assert fe.open.cbot_qty_tons == Decimal("700")
    assert fe.open.basis_qty_tons == Decimal("700")
    assert fe.open.fx_qty_tons == Decimal("700")
    assert fe.locked.cbot_qty_tons == Decimal("300")
    assert fe.locked.basis_qty_tons == Decimal("300")
    assert fe.locked.fx_qty_tons == Decimal("300")


def test_frame_with_cbot_and_fx_fixations() -> None:
    f = _frame("1000")
    fx1 = _fix(f.id, FixationMode.CBOT, "300", cbot="1420")
    fx2 = _fix(f.id, FixationMode.FX, "500", fxv="5.00")
    fe = open_exposure_frame(f, [fx1, fx2])
    # open: cbot 1000-300=700, basis 1000, fx 1000-500=500
    # locked: cbot 300, basis 0, fx 500
    assert fe.open.cbot_qty_tons == Decimal("700")
    assert fe.open.basis_qty_tons == Decimal("1000")
    assert fe.open.fx_qty_tons == Decimal("500")
    assert fe.locked.cbot_qty_tons == Decimal("300")
    assert fe.locked.basis_qty_tons == Decimal(0)
    assert fe.locked.fx_qty_tons == Decimal("500")


def test_frame_with_cbot_basis_fixation() -> None:
    f = _frame("1000")
    fx = _fix(f.id, FixationMode.CBOT_BASIS, "400", cbot="1420", basis="0.5")
    fe = open_exposure_frame(f, [fx])
    assert fe.open.cbot_qty_tons == Decimal("600")
    assert fe.open.basis_qty_tons == Decimal("600")
    assert fe.open.fx_qty_tons == Decimal("1000")
    assert fe.locked.cbot_qty_tons == Decimal("400")
    assert fe.locked.basis_qty_tons == Decimal("400")
    assert fe.locked.fx_qty_tons == Decimal(0)


def test_frame_with_basis_only_fixation() -> None:
    f = _frame("1000")
    fx = _fix(f.id, FixationMode.BASIS, "400", basis="0.5")
    fe = open_exposure_frame(f, [fx])
    assert fe.open.cbot_qty_tons == Decimal("1000")
    assert fe.open.basis_qty_tons == Decimal("600")
    assert fe.open.fx_qty_tons == Decimal("1000")
    assert fe.locked.basis_qty_tons == Decimal("400")


def test_frame_with_fx_only_fixation() -> None:
    f = _frame("1000")
    fx = _fix(f.id, FixationMode.FX, "400", fxv="5.00")
    fe = open_exposure_frame(f, [fx])
    assert fe.open.fx_qty_tons == Decimal("600")
    assert fe.locked.fx_qty_tons == Decimal("400")


# ---------------------------------------------------------------------------
# Over-locked leg raises DomainError
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mode", "qty", "expected_leg", "cbot", "basis", "fxv"),
    [
        (FixationMode.CBOT, "1200", "cbot", "1420", None, None),
        (FixationMode.BASIS, "1200", "basis", None, "0.5", None),
        (FixationMode.FX, "1200", "fx", None, None, "5.00"),
    ],
)
def test_over_locked_leg_raises(
    mode: FixationMode,
    qty: str,
    expected_leg: str,
    cbot: str | None,
    basis: str | None,
    fxv: str | None,
) -> None:
    f = _frame("1000")
    fx = _fix(f.id, mode, qty, cbot=cbot, basis=basis, fxv=fxv)
    with pytest.raises(DomainError, match=f"Over-locked leg {expected_leg}"):
        open_exposure_frame(f, [fx])


# ---------------------------------------------------------------------------
# aggregate_exposure
# ---------------------------------------------------------------------------


def _cbot_future(commodity: Commodity, side: Side, contracts: str) -> CBOTDerivative:
    return CBOTDerivative(
        id=uuid4(),
        user_id=uuid4(),
        commodity=commodity,
        instrument=CBOTInstrument.FUTURE,
        side=side,
        contract="ZSK26" if commodity == Commodity.SOJA else "ZCN26",
        quantity_contracts=Decimal(contracts),
        trade_date=date(2026, 4, 15),
        trade_price=Decimal("1420"),
        maturity_date=date(2026, 5, 15),
    )


def _basis_forward(commodity: Commodity, side: Side, qty: str) -> BasisForward:
    return BasisForward(
        id=uuid4(),
        user_id=uuid4(),
        commodity=commodity,
        side=side,
        quantity_tons=Decimal(qty),
        trade_date=date(2026, 4, 15),
        basis_price=Decimal("0.5"),
        delivery_date=date(2026, 7, 15),
        reference_cbot_contract="ZSK26",
    )


def _fx_ndf(side: Side, notional: str) -> FXDerivative:
    return FXDerivative(
        id=uuid4(),
        user_id=uuid4(),
        instrument=FXInstrument.NDF,
        side=side,
        notional_usd=Decimal(notional),
        trade_date=date(2026, 4, 15),
        trade_rate=Decimal("5.00"),
        maturity_date=date(2026, 7, 15),
    )


def test_aggregate_exposure_mixed_book() -> None:
    # Physical: 1000 tons soja buy, all open (no fixations) -> +1000 on every leg of SOJA
    frame_soja = _frame("1000", Commodity.SOJA, Side.BUY)

    # CBOT: sell 4 ZSK26 contracts -> -4 * 5000 / 36.744 = -544.1215...
    cbot_sell = _cbot_future(Commodity.SOJA, Side.SELL, "4")
    expected_cbot_tons = -(Decimal("4") * Decimal("5000") / Decimal("36.744"))

    # Basis forward: buy 200 tons milho basis
    basis_buy_milho = _basis_forward(Commodity.MILHO, Side.BUY, "200")

    # FX: sell 500_000 USD NDF -> -500000 on fx_notional_usd
    fx_sell = _fx_ndf(Side.SELL, "500000")

    agg = aggregate_exposure([(frame_soja, [])], [cbot_sell], [basis_buy_milho], [fx_sell])

    soja = agg.by_commodity[Commodity.SOJA]
    assert soja.cbot_qty_tons == Decimal("1000") + expected_cbot_tons
    assert soja.basis_qty_tons == Decimal("1000")
    assert soja.fx_qty_tons == Decimal("1000")

    milho = agg.by_commodity[Commodity.MILHO]
    assert milho.cbot_qty_tons == Decimal(0)
    assert milho.basis_qty_tons == Decimal("200")
    assert milho.fx_qty_tons == Decimal(0)

    assert agg.fx_notional_usd == Decimal("-500000")

    # Total is sum across commodities
    assert agg.total.cbot_qty_tons == soja.cbot_qty_tons + milho.cbot_qty_tons
    assert agg.total.basis_qty_tons == soja.basis_qty_tons + milho.basis_qty_tons
    assert agg.total.fx_qty_tons == soja.fx_qty_tons + milho.fx_qty_tons


def test_aggregate_exposure_empty_book_is_all_zeros() -> None:
    agg = aggregate_exposure([], [], [], [])
    for bucket in agg.by_commodity.values():
        assert bucket.cbot_qty_tons == Decimal(0)
        assert bucket.basis_qty_tons == Decimal(0)
        assert bucket.fx_qty_tons == Decimal(0)
    assert agg.fx_notional_usd == Decimal(0)
    assert agg.total.cbot_qty_tons == Decimal(0)


def test_aggregate_exposure_physical_sell_flips_sign() -> None:
    frame_sell = _frame("500", Commodity.MILHO, Side.SELL)
    agg = aggregate_exposure([(frame_sell, [])], [], [], [])
    milho = agg.by_commodity[Commodity.MILHO]
    assert milho.cbot_qty_tons == Decimal("-500")
    assert milho.basis_qty_tons == Decimal("-500")
    assert milho.fx_qty_tons == Decimal("-500")


def test_aggregate_exposure_cbot_european_option_contributes_via_delta() -> None:
    """Phase 8: european_option no longer raises. ATM call adds a delta-weighted tons-equiv."""
    from datetime import timedelta

    opt = CBOTDerivative(
        id=uuid4(),
        user_id=uuid4(),
        commodity=Commodity.SOJA,
        instrument=CBOTInstrument.EUROPEAN_OPTION,
        side=Side.BUY,
        contract="ZSK26",
        quantity_contracts=Decimal("1"),
        trade_date=date.today(),
        trade_price=Decimal("1420"),
        maturity_date=date.today() + timedelta(days=180),
        option_type=OptionType.CALL,
        strike=Decimal("1420"),
    )
    agg = aggregate_exposure([], [opt], [], [])
    # A 1-contract ATM call has delta ~0.5, so effective CBOT tons-equiv
    # ≈ 0.5 * 5000 / 36.744 ≈ 68 tons (positive because BUY).
    cbot = agg.by_commodity[Commodity.SOJA].cbot_qty_tons
    assert 50 < float(cbot) < 90


def test_aggregate_exposure_cbot_option_missing_strike_skips() -> None:
    opt = CBOTDerivative(
        id=uuid4(),
        user_id=uuid4(),
        commodity=Commodity.SOJA,
        instrument=CBOTInstrument.AMERICAN_OPTION,
        side=Side.BUY,
        contract="ZSK26",
        quantity_contracts=Decimal("1"),
        trade_date=date(2026, 4, 15),
        trade_price=Decimal("1420"),
        maturity_date=date(2026, 5, 15),
        option_type=OptionType.PUT,
        strike=None,
    )
    agg = aggregate_exposure([], [opt], [], [])
    assert agg.by_commodity[Commodity.SOJA].cbot_qty_tons == Decimal(0)


def test_aggregate_exposure_fx_option_contributes_via_delta() -> None:
    from datetime import timedelta

    opt = FXDerivative(
        id=uuid4(),
        user_id=uuid4(),
        instrument=FXInstrument.EUROPEAN_OPTION,
        side=Side.BUY,
        notional_usd=Decimal("100000"),
        trade_date=date.today(),
        trade_rate=Decimal("5.00"),
        maturity_date=date.today() + timedelta(days=90),
        option_type=OptionType.CALL,
        strike=Decimal("5.00"),
    )
    agg = aggregate_exposure([], [], [], [opt])
    # ATM FX call: delta ~0.5, signed notional ~ 50k USD
    assert 30_000 < float(agg.fx_notional_usd) < 70_000


def test_aggregate_exposure_cbot_swap_treated_as_linear() -> None:
    swap = CBOTDerivative(
        id=uuid4(),
        user_id=uuid4(),
        commodity=Commodity.SOJA,
        instrument=CBOTInstrument.SWAP,
        side=Side.BUY,
        contract="ZSK26",
        quantity_contracts=Decimal("2"),
        trade_date=date(2026, 4, 15),
        trade_price=Decimal("1420"),
        maturity_date=date(2026, 5, 15),
    )
    agg = aggregate_exposure([], [swap], [], [])
    expected = Decimal("2") * Decimal("5000") / Decimal("36.744")
    assert agg.by_commodity[Commodity.SOJA].cbot_qty_tons == expected
