"""Per-leg exposure aggregation for physical frames + derivatives.

Physical frames split a single contract's tonnage across three legs
(CBOT, basis, FX). A fixation "locks" one or more legs on a subset of
the tonnage; remaining tonnage stays open on that leg. `open_exposure_frame`
computes per-leg open and locked tons. `aggregate_exposure` rolls frames,
CBOT futures/swaps/options, basis forwards, and FX NDFs/options into a
signed per-commodity view. Options contribute via their *model delta*
(Phase 8 pricing engine) so a short OTM call dampens the linear CBOT
exposure rather than inflating it.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models.basis import BasisForward
from app.models.cbot import CBOTDerivative
from app.models.enums import (
    CBOTInstrument,
    Commodity,
    FixationMode,
    FXInstrument,
    Side,
)
from app.models.fx import FXDerivative
from app.models.physical import PhysicalFixation, PhysicalFrame
from app.risk.options.greeks import option_delta
from app.risk.pricing import TONS_TO_BUSHELS
from app.risk.types import (
    AggregateExposure,
    DomainError,
    FrameExposure,
    LegExposure,
    SignedLegExposure,
)

# Which legs each fixation mode locks.
_CBOT_LOCKING = {FixationMode.FLAT, FixationMode.CBOT, FixationMode.CBOT_BASIS}
_BASIS_LOCKING = {FixationMode.FLAT, FixationMode.CBOT_BASIS, FixationMode.BASIS}
_FX_LOCKING = {FixationMode.FLAT, FixationMode.FX}

# CBOT contract size for ZS (soja) and ZC (milho).
_CBOT_CONTRACT_SIZE_BU = Decimal("5000")

_OPTION_INSTRUMENTS: frozenset[CBOTInstrument | FXInstrument] = frozenset(
    {
        CBOTInstrument.EUROPEAN_OPTION,
        CBOTInstrument.AMERICAN_OPTION,
        CBOTInstrument.BARRIER_OPTION,
        FXInstrument.EUROPEAN_OPTION,
        FXInstrument.AMERICAN_OPTION,
        FXInstrument.BARRIER_OPTION,
    }
)


def _side_sign(side: Side) -> Decimal:
    return Decimal(1) if side is Side.BUY else Decimal(-1)


def _years_to_maturity(maturity: date, today: date | None = None) -> Decimal:
    ref = today or date.today()
    days = (maturity - ref).days
    if days <= 0:
        return Decimal(0)
    return Decimal(days) / Decimal("365.25")


def open_exposure_frame(frame: PhysicalFrame, fixations: list[PhysicalFixation]) -> FrameExposure:
    """Compute open + locked tons per leg for a single physical frame."""
    locked_cbot = Decimal(0)
    locked_basis = Decimal(0)
    locked_fx = Decimal(0)

    for fx in fixations:
        qty = fx.quantity_tons
        if fx.fixation_mode in _CBOT_LOCKING:
            locked_cbot += qty
        if fx.fixation_mode in _BASIS_LOCKING:
            locked_basis += qty
        if fx.fixation_mode in _FX_LOCKING:
            locked_fx += qty

    total = frame.quantity_tons
    for leg_name, locked in (
        ("cbot", locked_cbot),
        ("basis", locked_basis),
        ("fx", locked_fx),
    ):
        if locked > total:
            raise DomainError(f"Over-locked leg {leg_name}: {locked} > {total}")

    open_cbot = total - locked_cbot
    open_basis = total - locked_basis
    open_fx = total - locked_fx

    return FrameExposure(
        frame_id=frame.id,
        commodity=frame.commodity,
        side=frame.side,
        total_tons=total,
        open=LegExposure(
            cbot_qty_tons=open_cbot,
            basis_qty_tons=open_basis,
            fx_qty_tons=open_fx,
        ),
        locked=LegExposure(
            cbot_qty_tons=locked_cbot,
            basis_qty_tons=locked_basis,
            fx_qty_tons=locked_fx,
        ),
    )


def _empty_signed() -> SignedLegExposure:
    return SignedLegExposure(
        cbot_qty_tons=Decimal(0),
        basis_qty_tons=Decimal(0),
        fx_qty_tons=Decimal(0),
    )


def _add_cbot(target: SignedLegExposure, delta: Decimal) -> SignedLegExposure:
    return SignedLegExposure(
        cbot_qty_tons=target.cbot_qty_tons + delta,
        basis_qty_tons=target.basis_qty_tons,
        fx_qty_tons=target.fx_qty_tons,
    )


def _add_basis(target: SignedLegExposure, delta: Decimal) -> SignedLegExposure:
    return SignedLegExposure(
        cbot_qty_tons=target.cbot_qty_tons,
        basis_qty_tons=target.basis_qty_tons + delta,
        fx_qty_tons=target.fx_qty_tons,
    )


def _add_fx(target: SignedLegExposure, delta: Decimal) -> SignedLegExposure:
    return SignedLegExposure(
        cbot_qty_tons=target.cbot_qty_tons,
        basis_qty_tons=target.basis_qty_tons,
        fx_qty_tons=target.fx_qty_tons + delta,
    )


def aggregate_exposure(
    frames_with_fixations: list[tuple[PhysicalFrame, list[PhysicalFixation]]],
    cbot_derivs: list[CBOTDerivative],
    basis_fwds: list[BasisForward],
    fx_derivs: list[FXDerivative],
) -> AggregateExposure:
    """Net per-leg, per-commodity exposure plus a standalone FX notional bucket.

    Sign convention: buy=+1, sell=-1. Options raise NotImplementedError
    (linear engine only; option deltas arrive in Phase 8).
    """
    by_commodity: dict[Commodity, SignedLegExposure] = {c: _empty_signed() for c in Commodity}
    fx_notional_usd = Decimal(0)

    # Physical frames: each open leg contributes signed tons on that leg.
    for frame, fixations in frames_with_fixations:
        fe = open_exposure_frame(frame, fixations)
        sign = _side_sign(fe.side)
        bucket = by_commodity[fe.commodity]
        bucket = _add_cbot(bucket, sign * fe.open.cbot_qty_tons)
        bucket = _add_basis(bucket, sign * fe.open.basis_qty_tons)
        bucket = _add_fx(bucket, sign * fe.open.fx_qty_tons)
        by_commodity[fe.commodity] = bucket

    # CBOT futures/swaps/options: convert to tons-equivalent on the CBOT leg.
    for cd in cbot_derivs:
        bushels = TONS_TO_BUSHELS[cd.commodity]
        linear_tons = cd.quantity_contracts * _CBOT_CONTRACT_SIZE_BU / bushels
        if cd.instrument in _OPTION_INSTRUMENTS:
            years = _years_to_maturity(cd.maturity_date)
            if cd.strike is None or years <= 0:
                # No strike or already expired → no linear delta contribution.
                continue
            delta = option_delta(
                instrument=cd.instrument,
                spot=cd.trade_price,  # proxy for current spot; see module docstring
                strike=cd.strike,
                years_to_maturity=years,
                option_type=cd.option_type,
                barrier_type=cd.barrier_type,
                barrier_level=cd.barrier_level,
                rebate=cd.rebate,
            )
            effective_tons = linear_tons * delta
        else:
            effective_tons = linear_tons
        bucket = by_commodity[cd.commodity]
        bucket = _add_cbot(bucket, _side_sign(cd.side) * effective_tons)
        by_commodity[cd.commodity] = bucket

    # Basis forwards: signed tons on the basis leg.
    for bf in basis_fwds:
        bucket = by_commodity[bf.commodity]
        bucket = _add_basis(bucket, _side_sign(bf.side) * bf.quantity_tons)
        by_commodity[bf.commodity] = bucket

    # FX derivatives: add signed USD notional to the dedicated bucket.
    # FX options contribute `notional × delta` (delta from the pricing model).
    for fxd in fx_derivs:
        if fxd.instrument in _OPTION_INSTRUMENTS:
            years = _years_to_maturity(fxd.maturity_date)
            if fxd.strike is None or years <= 0:
                continue
            delta = option_delta(
                instrument=fxd.instrument,
                spot=fxd.trade_rate,
                strike=fxd.strike,
                years_to_maturity=years,
                option_type=fxd.option_type,
                barrier_type=fxd.barrier_type,
                barrier_level=fxd.barrier_level,
                rebate=fxd.rebate,
            )
            fx_notional_usd += _side_sign(fxd.side) * fxd.notional_usd * delta
        else:
            fx_notional_usd += _side_sign(fxd.side) * fxd.notional_usd

    total = SignedLegExposure(
        cbot_qty_tons=sum((b.cbot_qty_tons for b in by_commodity.values()), start=Decimal(0)),
        basis_qty_tons=sum((b.basis_qty_tons for b in by_commodity.values()), start=Decimal(0)),
        fx_qty_tons=sum((b.fx_qty_tons for b in by_commodity.values()), start=Decimal(0)),
    )

    return AggregateExposure(
        by_commodity=by_commodity,
        total=total,
        fx_notional_usd=fx_notional_usd,
    )
