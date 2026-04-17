"""Stress testing: hand-specified shocks applied via the shared pricing model.

All P&L math funnels through `risk.pricing.mtm_value_brl` — there is no
inline arithmetic here. Historical scenarios mirror
`.claude/skills/risk-engine-patterns/references/stress_scenarios.md`;
basis shocks default to zero but the dataclass carries them so users can
build custom scenarios that shock basis too.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TypedDict

from app.models.enums import Commodity
from app.risk.pricing import mtm_value_brl
from app.risk.types import (
    AggregateExposure,
    HistoricalScenario,
    Leg,
    StressResult,
)

HISTORICAL_SCENARIOS: tuple[HistoricalScenario, ...] = (
    HistoricalScenario(
        name="2008 GFC",
        cbot_soja=Decimal("-0.35"),
        cbot_milho=Decimal("-0.42"),
        basis_soja=Decimal("0"),
        basis_milho=Decimal("0"),
        fx=Decimal("0.40"),
        source_period="Sep-Dec 2008",
    ),
    HistoricalScenario(
        name="2012 US Drought",
        cbot_soja=Decimal("0.35"),
        cbot_milho=Decimal("0.45"),
        basis_soja=Decimal("0"),
        basis_milho=Decimal("0"),
        fx=Decimal("0.08"),
        source_period="Jun-Aug 2012",
    ),
    HistoricalScenario(
        name="2020 COVID",
        cbot_soja=Decimal("-0.12"),
        cbot_milho=Decimal("-0.18"),
        basis_soja=Decimal("0"),
        basis_milho=Decimal("0"),
        fx=Decimal("0.35"),
        source_period="Mar 2020",
    ),
    HistoricalScenario(
        name="2022 Ukraine War",
        cbot_soja=Decimal("0.25"),
        cbot_milho=Decimal("0.30"),
        basis_soja=Decimal("0"),
        basis_milho=Decimal("0"),
        fx=Decimal("-0.05"),
        source_period="Feb-May 2022",
    ),
)


class CurrentPrices(TypedDict, total=False):
    cbot_soja: Decimal  # USc/bu
    cbot_milho: Decimal
    fx: Decimal  # BRL/USD
    basis_soja: Decimal  # USD/bu
    basis_milho: Decimal


def _commodity_inputs(
    prices: CurrentPrices, commodity: Commodity
) -> tuple[Decimal, Decimal, Decimal]:
    fx = prices.get("fx", Decimal(0))
    if commodity is Commodity.SOJA:
        return (
            prices.get("cbot_soja", Decimal(0)),
            fx,
            prices.get("basis_soja", Decimal(0)),
        )
    return (
        prices.get("cbot_milho", Decimal(0)),
        fx,
        prices.get("basis_milho", Decimal(0)),
    )


def _shocked_inputs(
    prices: CurrentPrices, scenario: HistoricalScenario, commodity: Commodity
) -> tuple[Decimal, Decimal, Decimal]:
    cbot, fx, basis = _commodity_inputs(prices, commodity)
    if commodity is Commodity.SOJA:
        shocked_cbot = cbot * (Decimal(1) + scenario.cbot_soja)
        shocked_basis = basis * (Decimal(1) + scenario.basis_soja)
    else:
        shocked_cbot = cbot * (Decimal(1) + scenario.cbot_milho)
        shocked_basis = basis * (Decimal(1) + scenario.basis_milho)
    shocked_fx = fx * (Decimal(1) + scenario.fx)
    return shocked_cbot, shocked_fx, shocked_basis


def apply_scenario(
    exposure: AggregateExposure,
    prices_current: CurrentPrices,
    scenario: HistoricalScenario,
) -> StressResult:
    """Apply scenario shocks to each commodity leg and return signed P&L.

    Interpretation: the `cbot` leg's tons contribute P&L only when the
    CBOT factor moves; same for FX. The basis leg moves independently via
    `basis_*` shocks. All P&L is computed by repricing with `mtm_value_brl`.
    """
    total_pnl = Decimal(0)
    per_commodity: dict[Commodity, Decimal] = {c: Decimal(0) for c in Commodity}
    per_leg: dict[Leg, Decimal] = {"cbot": Decimal(0), "basis": Decimal(0), "fx": Decimal(0)}

    for commodity, exp in exposure.by_commodity.items():
        cbot_cur, fx_cur, basis_cur = _commodity_inputs(prices_current, commodity)
        cbot_shk, fx_shk, basis_shk = _shocked_inputs(prices_current, scenario, commodity)

        # Isolated per-leg P&L: move one factor at a time, keep others at current.
        # CBOT leg: exposure on CBOT × (price(shk_cbot) - price(cur_cbot)) at current FX/basis.
        cbot_pnl = mtm_value_brl(
            commodity, exp.cbot_qty_tons, cbot_shk, fx_cur, basis_cur
        ) - mtm_value_brl(commodity, exp.cbot_qty_tons, cbot_cur, fx_cur, basis_cur)
        basis_pnl = mtm_value_brl(
            commodity, exp.basis_qty_tons, cbot_cur, fx_cur, basis_shk
        ) - mtm_value_brl(commodity, exp.basis_qty_tons, cbot_cur, fx_cur, basis_cur)
        fx_pnl = mtm_value_brl(
            commodity, exp.fx_qty_tons, cbot_cur, fx_shk, basis_cur
        ) - mtm_value_brl(commodity, exp.fx_qty_tons, cbot_cur, fx_cur, basis_cur)
        commodity_pnl = cbot_pnl + basis_pnl + fx_pnl
        per_commodity[commodity] += commodity_pnl
        per_leg["cbot"] += cbot_pnl
        per_leg["basis"] += basis_pnl
        per_leg["fx"] += fx_pnl
        total_pnl += commodity_pnl

    return StressResult(
        scenario_name=scenario.name,
        total_pnl_brl=total_pnl,
        per_commodity_pnl=per_commodity,
        per_leg_pnl=per_leg,
    )


def run_all_historical(
    exposure: AggregateExposure, prices_current: CurrentPrices
) -> list[StressResult]:
    return [apply_scenario(exposure, prices_current, s) for s in HISTORICAL_SCENARIOS]
