"""Risk engine endpoints: VaR, CVaR, stress scenarios, recalc hook.

For Phase 6, the endpoints accept an explicit `portfolio` payload
(weights + current factor prices) and read the price history from the
`prices` table to build the returns series. Auto-deriving weights from
the user's open positions is deferred to Phase 7 when the
attribution/component-VaR layer lands.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

import pandas as pd
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import UserPrincipal, get_current_user
from app.models.enums import Commodity
from app.models.prices import Price
from app.risk.attribution import component_var
from app.risk.correlation import correlation_matrix
from app.risk.cvar import expected_shortfall
from app.risk.mc import fan_chart_paths
from app.risk.returns import align_multi_series, compute_returns
from app.risk.stress import (
    HISTORICAL_SCENARIOS,
    CurrentPrices,
    apply_scenario,
    run_all_historical,
)
from app.risk.types import (
    AggregateExposure,
    CVaRResult,
    HistoricalScenario,
    Leg,
    PositionWeight,
    SignedLegExposure,
    StressResult,
    VaRMethod,
    VaRResult,
)
from app.risk.var import historical_var, monte_carlo_var, parametric_var

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/risk", tags=["risk"])


# --------------------------------------------------------------------------- #
# Request / response models
# --------------------------------------------------------------------------- #


class VarRequest(BaseModel):
    method: VaRMethod
    confidence: Decimal = Field(default=Decimal("0.95"))
    horizon_days: int = Field(default=1, ge=1)
    window: int = Field(default=252, ge=10)
    n_paths: int = Field(default=10_000, ge=100)
    seed: int | None = None
    weights: dict[str, Decimal] = Field(
        default_factory=dict,
        description='BRL exposure per factor (keys like "ZS=F", "ZC=F", "USDBRL=X")',
    )


class CVarRequest(VarRequest):
    confidence: Decimal = Field(default=Decimal("0.975"))


class VaRResponse(BaseModel):
    method: VaRMethod
    confidence: Decimal
    horizon_days: int
    value_brl: Decimal
    per_leg: dict[Leg, Decimal]
    n_observations: int
    seed: int | None = None


class CVaRResponse(VaRResponse):
    pass


class StressRequest(BaseModel):
    exposure_tons_by_commodity: dict[Literal["soja", "milho"], dict[Leg, Decimal]] = Field(
        default_factory=dict
    )
    prices_current: CurrentPrices


class CustomScenarioBody(BaseModel):
    scenario_id: UUID | None = None
    scenario: HistoricalScenario | None = None
    exposure_tons_by_commodity: dict[Literal["soja", "milho"], dict[Leg, Decimal]]
    prices_current: CurrentPrices


class StressResponseRow(BaseModel):
    scenario_name: str
    total_pnl_brl: Decimal
    per_commodity_pnl: dict[str, Decimal]
    per_leg_pnl: dict[Leg, Decimal]


class RecalculateResponse(BaseModel):
    status: str
    recalculated_at: datetime


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _detail(title: str) -> dict[str, object]:
    return {"type": "about:blank", "title": title}


def _to_va_response(r: VaRResult) -> VaRResponse:
    return VaRResponse(
        method=r.method,
        confidence=r.confidence,
        horizon_days=r.horizon_days,
        value_brl=r.value_brl,
        per_leg=r.per_leg,
        n_observations=r.n_observations,
        seed=r.seed,
    )


def _to_cva_response(r: CVaRResult) -> CVaRResponse:
    return CVaRResponse(
        method=r.method,
        confidence=r.confidence,
        horizon_days=r.horizon_days,
        value_brl=r.value_brl,
        per_leg=r.per_leg,
        n_observations=r.n_observations,
        seed=r.seed,
    )


def _build_exposure(
    spec: dict[Literal["soja", "milho"], dict[Leg, Decimal]],
) -> AggregateExposure:
    by_commodity: dict[Commodity, SignedLegExposure] = {}
    total_cbot = Decimal(0)
    total_basis = Decimal(0)
    total_fx = Decimal(0)
    for key, legs in spec.items():
        commodity = Commodity(key)
        sle = SignedLegExposure(
            cbot_qty_tons=legs.get("cbot", Decimal(0)),
            basis_qty_tons=legs.get("basis", Decimal(0)),
            fx_qty_tons=legs.get("fx", Decimal(0)),
        )
        by_commodity[commodity] = sle
        total_cbot += sle.cbot_qty_tons
        total_basis += sle.basis_qty_tons
        total_fx += sle.fx_qty_tons
    # Fill in missing commodities with zero
    for c in Commodity:
        by_commodity.setdefault(
            c,
            SignedLegExposure(
                cbot_qty_tons=Decimal(0), basis_qty_tons=Decimal(0), fx_qty_tons=Decimal(0)
            ),
        )
    return AggregateExposure(
        by_commodity=by_commodity,
        total=SignedLegExposure(total_cbot, total_basis, total_fx),
    )


def _result_to_row(r: StressResult) -> StressResponseRow:
    return StressResponseRow(
        scenario_name=r.scenario_name,
        total_pnl_brl=r.total_pnl_brl,
        per_commodity_pnl={c.value: v for c, v in r.per_commodity_pnl.items()},
        per_leg_pnl=r.per_leg_pnl,
    )


async def _load_returns(session: AsyncSession, instruments: list[str], window: int) -> pd.DataFrame:
    """Load up to `window * 2` most recent observations per instrument."""
    if not instruments:
        return pd.DataFrame()
    stmt = (
        select(Price.observed_at, Price.instrument, Price.value)
        .where(Price.instrument.in_(instruments))
        .order_by(Price.observed_at.asc())
    )
    rows = (await session.execute(stmt)).all()
    series_by_instrument: dict[str, pd.Series] = {}
    for instr in instruments:
        filtered = [(r.observed_at, float(r.value)) for r in rows if r.instrument == instr]
        if not filtered:
            continue
        idx, vals = zip(*filtered, strict=True)
        series_by_instrument[instr] = pd.Series(
            list(vals), index=pd.DatetimeIndex(list(idx), name="observed_at")
        )
    aligned = align_multi_series(series_by_instrument)
    if len(aligned) < 2:
        return pd.DataFrame()
    returns = compute_returns(aligned, kind="log")
    return returns.tail(window * 2)


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #


@router.post("/var", response_model=VaRResponse)
async def var_endpoint(
    body: VarRequest,
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> VaRResponse:
    instruments = list(body.weights.keys())
    returns = await _load_returns(session, instruments, body.window)
    if returns.empty:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=_detail("not enough price history to compute VaR"),
        )
    logger.info(
        "risk.var",
        method=body.method,
        confidence=str(body.confidence),
        horizon_days=body.horizon_days,
        n_observations=len(returns),
        user_id=str(principal.id),
    )
    if body.method == "historical":
        result = historical_var(
            returns, body.weights, body.confidence, body.horizon_days, body.window
        )
    elif body.method == "parametric":
        result = parametric_var(returns, body.weights, body.confidence, body.horizon_days)
    else:  # monte_carlo
        result = monte_carlo_var(
            returns,
            body.weights,
            body.confidence,
            body.horizon_days,
            body.n_paths,
            body.seed,
        )
    return _to_va_response(result)


@router.post("/cvar", response_model=CVaRResponse)
async def cvar_endpoint(
    body: CVarRequest,
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CVaRResponse:
    instruments = list(body.weights.keys())
    returns = await _load_returns(session, instruments, body.window)
    if returns.empty:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=_detail("not enough price history to compute CVaR"),
        )
    logger.info(
        "risk.cvar",
        method=body.method,
        confidence=str(body.confidence),
        horizon_days=body.horizon_days,
        n_observations=len(returns),
        user_id=str(principal.id),
    )
    result = expected_shortfall(
        returns,
        body.weights,
        body.confidence,
        body.horizon_days,
        body.method,
        body.window,
        body.n_paths,
        body.seed,
    )
    return _to_cva_response(result)


@router.post("/stress/historical", response_model=list[StressResponseRow])
async def stress_historical(
    body: StressRequest,
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
) -> list[StressResponseRow]:
    exposure = _build_exposure(body.exposure_tons_by_commodity)
    results = run_all_historical(exposure, body.prices_current)
    logger.info(
        "risk.stress.historical",
        scenarios=len(results),
        user_id=str(principal.id),
    )
    return [_result_to_row(r) for r in results]


@router.post("/stress/custom", response_model=StressResponseRow)
async def stress_custom(
    body: CustomScenarioBody,
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
) -> StressResponseRow:
    if body.scenario is None and body.scenario_id is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=_detail("provide either scenario or scenario_id"),
        )
    scenario = body.scenario
    if scenario is None:
        # DB-loaded scenarios can be added in a later phase; for now require
        # an inline scenario payload so this endpoint is callable standalone.
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            detail=_detail("scenario_id lookup not implemented yet; pass scenario inline"),
        )
    exposure = _build_exposure(body.exposure_tons_by_commodity)
    result = apply_scenario(exposure, body.prices_current, scenario)
    logger.info(
        "risk.stress.custom",
        scenario=scenario.name,
        user_id=str(principal.id),
    )
    return _result_to_row(result)


@router.post("/recalculate", response_model=RecalculateResponse)
async def recalculate(
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
) -> RecalculateResponse:
    """Stub hit by the Airflow DAG after a price upsert. Real cache-warm in a later phase."""
    logger.info("risk.recalculate", user_id=str(principal.id))
    return RecalculateResponse(status="ok", recalculated_at=datetime.now(tz=UTC))


# --------------------------------------------------------------------------- #
# Phase 7 additions: MC fan chart, correlation, component VaR
# --------------------------------------------------------------------------- #


class FanChartRequest(BaseModel):
    weights: dict[str, Decimal] = Field(default_factory=dict)
    horizon_days: int = Field(default=10, ge=1, le=252)
    n_paths: int = Field(default=10_000, ge=100)
    seed: int | None = None
    window: int = Field(default=252, ge=10)


class FanChartResponse(BaseModel):
    percentiles: dict[int, list[Decimal]]
    horizon_days: int
    n_paths: int
    seed: int


class CorrelationResponse(BaseModel):
    names: list[str]
    matrix: list[list[Decimal]]
    window: int
    n_observations: int


class PositionWeightIn(BaseModel):
    position_id: UUID
    label: str
    weight_brl: Decimal
    factor_exposures: dict[str, Decimal]


class AttributionRequest(BaseModel):
    positions: list[PositionWeightIn]
    confidence: Decimal = Field(default=Decimal("0.95"))
    horizon_days: int = Field(default=1, ge=1)
    window: int = Field(default=252, ge=10)


class PositionContributionOut(BaseModel):
    position_id: UUID
    label: str
    contribution_brl: Decimal
    share_pct: Decimal


@router.post("/mc/fan", response_model=FanChartResponse)
async def mc_fan(
    body: FanChartRequest,
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> FanChartResponse:
    instruments = list(body.weights.keys())
    returns = await _load_returns(session, instruments, body.window)
    if returns.empty:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=_detail("not enough price history for the fan chart"),
        )
    result = fan_chart_paths(
        body.weights,
        returns,
        horizon_days=body.horizon_days,
        n_paths=body.n_paths,
        seed=body.seed,
    )
    logger.info(
        "risk.mc.fan",
        horizon_days=result.horizon_days,
        n_paths=result.n_paths,
        seed=result.seed,
        n_observations=len(returns),
        user_id=str(principal.id),
    )
    return FanChartResponse(
        percentiles=result.percentiles,
        horizon_days=result.horizon_days,
        n_paths=result.n_paths,
        seed=result.seed,
    )


@router.get("/correlation", response_model=CorrelationResponse)
async def correlation_endpoint(
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    window: int = 252,
    instruments: list[str] | None = None,
) -> CorrelationResponse:
    default_instruments = ["ZS=F", "ZC=F", "USDBRL=X"]
    target = instruments if instruments else default_instruments
    returns = await _load_returns(session, target, window)
    if returns.empty:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=_detail("not enough price history for a correlation matrix"),
        )
    df = returns.tail(window)
    matrix, names = correlation_matrix(df)
    logger.info(
        "risk.correlation",
        window=window,
        n_observations=len(df),
        n_factors=len(names),
        user_id=str(principal.id),
    )
    return CorrelationResponse(
        names=names,
        matrix=[[Decimal(str(float(x))) for x in row] for row in matrix],
        window=window,
        n_observations=len(df),
    )


@router.post("/attribution", response_model=list[PositionContributionOut])
async def attribution_endpoint(
    body: AttributionRequest,
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[PositionContributionOut]:
    if not body.positions:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=_detail("attribution requires at least one position"),
        )
    # Collect all factors referenced by any position so we load the right
    # price history.
    factor_set: set[str] = set()
    for p in body.positions:
        factor_set.update(p.factor_exposures.keys())
    returns = await _load_returns(session, sorted(factor_set), body.window)
    if returns.empty:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=_detail("not enough price history to attribute VaR"),
        )

    positions = [
        PositionWeight(
            position_id=p.position_id,
            label=p.label,
            weight_brl=p.weight_brl,
            factor_exposures=p.factor_exposures,
        )
        for p in body.positions
    ]
    contributions = component_var(
        positions,
        returns,
        confidence=body.confidence,
        horizon_days=body.horizon_days,
    )
    logger.info(
        "risk.attribution",
        n_positions=len(positions),
        confidence=str(body.confidence),
        horizon_days=body.horizon_days,
        user_id=str(principal.id),
    )
    return [
        PositionContributionOut(
            position_id=c.position_id,
            label=c.label,
            contribution_brl=c.contribution_brl,
            share_pct=c.share_pct,
        )
        for c in contributions
    ]


# Reference for callers that want to see the built-in scenarios without auth metadata hacks.
BUILTIN_SCENARIOS: tuple[HistoricalScenario, ...] = HISTORICAL_SCENARIOS
