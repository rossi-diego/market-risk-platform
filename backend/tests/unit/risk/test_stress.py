"""Unit tests for stress scenarios."""

from __future__ import annotations

from decimal import Decimal

from app.models.enums import Commodity
from app.risk.pricing import mtm_value_brl
from app.risk.stress import (
    HISTORICAL_SCENARIOS,
    CurrentPrices,
    apply_scenario,
    run_all_historical,
)
from app.risk.types import AggregateExposure, SignedLegExposure


def _buy_1000t_soja() -> AggregateExposure:
    sle = SignedLegExposure(
        cbot_qty_tons=Decimal("1000"),
        basis_qty_tons=Decimal("1000"),
        fx_qty_tons=Decimal("1000"),
    )
    empty = SignedLegExposure(Decimal(0), Decimal(0), Decimal(0))
    return AggregateExposure(
        by_commodity={Commodity.SOJA: sle, Commodity.MILHO: empty},
        total=sle,
    )


def _current_prices() -> CurrentPrices:
    return {
        "cbot_soja": Decimal("1000"),
        "cbot_milho": Decimal("400"),
        "fx": Decimal("5"),
        "basis_soja": Decimal("0.5"),
        "basis_milho": Decimal("0.3"),
    }


def test_gfc_scenario() -> None:
    """2008 GFC: soja CBOT -35%, FX +40%. Hand-check P&L on 1000t soja buy."""
    exposure = _buy_1000t_soja()
    prices = _current_prices()
    gfc = next(s for s in HISTORICAL_SCENARIOS if s.name == "2008 GFC")
    result = apply_scenario(exposure, prices, gfc)

    cbot_cur = prices["cbot_soja"]
    fx_cur = prices["fx"]
    basis_cur = prices["basis_soja"]
    cbot_shk = cbot_cur * Decimal("0.65")  # -35%
    fx_shk = fx_cur * Decimal("1.40")  # +40%

    expected_cbot_pnl = mtm_value_brl(
        Commodity.SOJA, Decimal("1000"), cbot_shk, fx_cur, basis_cur
    ) - mtm_value_brl(Commodity.SOJA, Decimal("1000"), cbot_cur, fx_cur, basis_cur)
    expected_fx_pnl = mtm_value_brl(
        Commodity.SOJA, Decimal("1000"), cbot_cur, fx_shk, basis_cur
    ) - mtm_value_brl(Commodity.SOJA, Decimal("1000"), cbot_cur, fx_cur, basis_cur)
    expected_total = expected_cbot_pnl + expected_fx_pnl  # basis shock is 0
    assert result.per_leg_pnl["cbot"] == expected_cbot_pnl
    assert result.per_leg_pnl["fx"] == expected_fx_pnl
    assert result.total_pnl_brl == expected_total
    # CBOT -35% on a BUY position → negative P&L; FX +40% helps a sell of USD
    # but soja is priced in USD so a weaker BRL (+FX) increases BRL value →
    # positive P&L on this leg. Flag signs explicitly.
    assert result.per_leg_pnl["cbot"] < 0
    assert result.per_leg_pnl["fx"] > 0


def test_run_all_historical_returns_4_scenarios() -> None:
    exposure = _buy_1000t_soja()
    prices = _current_prices()
    results = run_all_historical(exposure, prices)
    assert len(results) == 4
    names = [r.scenario_name for r in results]
    assert "2008 GFC" in names
    assert "2012 US Drought" in names
    assert "2020 COVID" in names
    assert "2022 Ukraine War" in names


def test_custom_scenario_isolates_shocked_leg() -> None:
    """Shock only CBOT soja -10%. Milho = 0, FX = 0, soja < 0 on a buy."""
    from app.risk.types import HistoricalScenario

    custom = HistoricalScenario(
        name="custom-cbot-only",
        cbot_soja=Decimal("-0.10"),
        cbot_milho=Decimal("0"),
        basis_soja=Decimal("0"),
        basis_milho=Decimal("0"),
        fx=Decimal("0"),
        source_period="synthetic",
    )
    exposure = _buy_1000t_soja()
    prices = _current_prices()
    result = apply_scenario(exposure, prices, custom)

    assert result.per_commodity_pnl[Commodity.MILHO] == 0
    assert result.per_leg_pnl["fx"] == 0
    assert result.per_leg_pnl["basis"] == 0
    assert result.per_leg_pnl["cbot"] < 0
    assert result.per_commodity_pnl[Commodity.SOJA] < 0


def test_historical_scenarios_count() -> None:
    assert len(HISTORICAL_SCENARIOS) == 4
