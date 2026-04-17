"""Unified option-delta dispatcher used by exposure aggregation.

Converts a CBOT / FX option's delta into a BRL/ton sensitivity so it can be
added to the linear CBOT or FX leg in `aggregate_exposure`.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from app.models.enums import BarrierType, CBOTInstrument, Commodity, FXInstrument, OptionType
from app.risk.options.barrier import barrier_mc
from app.risk.options.binomial import crr_american
from app.risk.options.bsm import bsm_price

# Rough defaults used when the caller hasn't supplied per-option market data.
# These are reasonable starting points for a bookkeeping delta; for live risk
# the API boundary should pass concrete r/sigma/T/q pulled from the market.
_DEFAULT_RATE = Decimal("0.05")
_DEFAULT_SIGMA = Decimal("0.25")
_DEFAULT_DIVIDEND = Decimal("0")

_BARRIER_MAP: dict[BarrierType, str] = {
    BarrierType.UP_AND_IN: "up_and_in",
    BarrierType.UP_AND_OUT: "up_and_out",
    BarrierType.DOWN_AND_IN: "down_and_in",
    BarrierType.DOWN_AND_OUT: "down_and_out",
}


def _option_type_str(option_type: OptionType | None) -> Literal["call", "put"]:
    if option_type is OptionType.PUT:
        return "put"
    return "call"


def option_delta(
    *,
    instrument: CBOTInstrument | FXInstrument,
    spot: Decimal,
    strike: Decimal,
    years_to_maturity: Decimal,
    option_type: OptionType | None,
    barrier_type: BarrierType | None = None,
    barrier_level: Decimal | None = None,
    rebate: Decimal | None = None,
    rate: Decimal = _DEFAULT_RATE,
    sigma: Decimal = _DEFAULT_SIGMA,
    dividend_yield: Decimal = _DEFAULT_DIVIDEND,
    seed: int | None = None,
) -> Decimal:
    """Return the model delta (dPrice/dSpot) for a given option instrument."""
    kind = _option_type_str(option_type)

    if instrument in (CBOTInstrument.EUROPEAN_OPTION, FXInstrument.EUROPEAN_OPTION):
        res = bsm_price(spot, strike, years_to_maturity, rate, sigma, kind, dividend_yield)
        return res.delta
    if instrument in (CBOTInstrument.AMERICAN_OPTION, FXInstrument.AMERICAN_OPTION):
        res = crr_american(
            spot, strike, years_to_maturity, rate, sigma, kind, dividend_yield, n_steps=200
        )
        return res.delta
    if instrument in (CBOTInstrument.BARRIER_OPTION, FXInstrument.BARRIER_OPTION):
        if barrier_type is None or barrier_level is None:
            raise ValueError("barrier options require barrier_type and barrier_level")
        res = barrier_mc(
            spot,
            strike,
            years_to_maturity,
            rate,
            sigma,
            kind,
            _BARRIER_MAP[barrier_type],  # type: ignore[arg-type]
            barrier_level,
            rebate or Decimal("0"),
            dividend_yield,
            n_paths=10_000,
            n_steps=100,
            seed=seed,
        )
        return res.delta
    raise ValueError(f"not an option instrument: {instrument!r}")


# Commodity to bushels-per-ton (kept local to avoid a circular import with
# risk.pricing when aggregation wires this in).
_BUSHELS_PER_TON: dict[Commodity, Decimal] = {
    Commodity.SOJA: Decimal("36.744"),
    Commodity.MILHO: Decimal("56.0"),
}


def cbot_option_delta_brl_ton(
    *,
    instrument: CBOTInstrument,
    commodity: Commodity,
    fx_brl_usd: Decimal,
    spot_uscbu: Decimal,
    strike_uscbu: Decimal,
    years_to_maturity: Decimal,
    option_type: OptionType | None,
    barrier_type: BarrierType | None = None,
    barrier_level: Decimal | None = None,
    rebate: Decimal | None = None,
    rate: Decimal = _DEFAULT_RATE,
    sigma: Decimal = _DEFAULT_SIGMA,
    seed: int | None = None,
) -> Decimal:
    """BRL/ton delta of a CBOT option for a +1 USc/bu move in the underlying."""
    delta = option_delta(
        instrument=instrument,
        spot=spot_uscbu,
        strike=strike_uscbu,
        years_to_maturity=years_to_maturity,
        option_type=option_type,
        barrier_type=barrier_type,
        barrier_level=barrier_level,
        rebate=rebate,
        rate=rate,
        sigma=sigma,
        seed=seed,
    )
    bushels = _BUSHELS_PER_TON[commodity]
    # A +1 USc/bu move on the underlying scales to BRL/ton via the same
    # conversion used in risk.pricing.cbot_delta_brl_ton: fx / 100 / bushels.
    return delta * fx_brl_usd / Decimal("100") / bushels
