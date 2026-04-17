"""Price formation + unit-conversion math.

All conversion arithmetic in the codebase must live here. No inline math
elsewhere. Every function is pure and operates on `Decimal`; `float` is
forbidden in the financial path.

Price formation (CLAUDE.md > Price Formation Model):

    P_BRL_ton = (CBOT_USc_bu / 100 / bushels_per_ton) * FX_BRL_USD
              + premium_USD_bu * FX_BRL_USD / bushels_per_ton

Conversion factors (metric tons -> bushels):

    soja  = 36.744
    milho = 56.0

Per-leg sensitivities ("Greeks" in the linear sense):

    dP/dCBOT   (1 USc/bu shock)        = FX / 100 / bushels_per_ton
    dP/dFX     (0.01 BRL/USD shock)    = (CBOT/100/bushels + premium/bushels) * 0.01
    dP/dBASIS  (1 USD/bu shock)        = FX / bushels_per_ton
"""

from __future__ import annotations

from decimal import Decimal

from app.models.enums import Commodity

_CENTS_PER_DOLLAR = Decimal("100")
_FX_TICK = Decimal("0.01")  # one basis-point-like tick = 0.01 BRL/USD

TONS_TO_BUSHELS: dict[Commodity, Decimal] = {
    Commodity.SOJA: Decimal("36.744"),
    Commodity.MILHO: Decimal("56.0"),
}


def _bushels_per_ton(commodity: Commodity) -> Decimal:
    return TONS_TO_BUSHELS[commodity]


def price_brl_ton(
    commodity: Commodity,
    cbot_uscbu: Decimal,
    fx_brl_usd: Decimal,
    premium_usd_bu: Decimal,
) -> Decimal:
    """Composite BRL/ton price from CBOT (USc/bu), FX (BRL/USD), basis (USD/bu)."""
    bushels = _bushels_per_ton(commodity)
    cbot_component = (cbot_uscbu / _CENTS_PER_DOLLAR / bushels) * fx_brl_usd
    basis_component = premium_usd_bu * fx_brl_usd / bushels
    return cbot_component + basis_component


def mtm_value_brl(
    commodity: Commodity,
    quantity_tons: Decimal,
    cbot_uscbu: Decimal,
    fx_brl_usd: Decimal,
    premium_usd_bu: Decimal,
) -> Decimal:
    """Total BRL mark-to-market value of `quantity_tons` at the given inputs."""
    return price_brl_ton(commodity, cbot_uscbu, fx_brl_usd, premium_usd_bu) * quantity_tons


def cbot_delta_brl_ton(commodity: Commodity, fx_brl_usd: Decimal) -> Decimal:
    """Sensitivity of BRL/ton to a +1 USc/bu CBOT move."""
    return fx_brl_usd / _CENTS_PER_DOLLAR / _bushels_per_ton(commodity)


def fx_delta_brl_ton(commodity: Commodity, cbot_uscbu: Decimal, premium_usd_bu: Decimal) -> Decimal:
    """Sensitivity of BRL/ton to a +0.01 BRL/USD FX move."""
    bushels = _bushels_per_ton(commodity)
    return (cbot_uscbu / _CENTS_PER_DOLLAR / bushels + premium_usd_bu / bushels) * _FX_TICK


def basis_delta_brl_ton(commodity: Commodity, fx_brl_usd: Decimal) -> Decimal:
    """Sensitivity of BRL/ton to a +1 USD/bu basis move."""
    return fx_brl_usd / _bushels_per_ton(commodity)
