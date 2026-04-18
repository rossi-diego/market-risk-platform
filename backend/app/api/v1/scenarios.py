"""CRUD for user scenarios + read-only access to the 4 built-in templates.

Templates live in `scenarios_templates` (populated by the Phase 2 migration) and
are seen by every authenticated user. User-created scenarios live in
`scenarios` and are always filtered by `user_id`.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import UserPrincipal, get_current_user
from app.models.config import Scenario, ScenarioTemplate
from app.schemas.config import (
    ScenarioIn,
    ScenarioOut,
    ScenarioTemplateOut,
    ScenarioUpdate,
)

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


def _detail(title: str, extra: dict[str, object] | None = None) -> dict[str, object]:
    body: dict[str, object] = {"type": "about:blank", "title": title}
    if extra:
        body.update(extra)
    return body


@router.get("/templates", response_model=list[ScenarioTemplateOut])
async def list_templates(
    _: Annotated[UserPrincipal, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ScenarioTemplate]:
    stmt = select(ScenarioTemplate).order_by(ScenarioTemplate.created_at.asc())
    return list((await session.execute(stmt)).scalars().all())


@router.get("", response_model=list[ScenarioOut])
async def list_scenarios(
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[Scenario]:
    stmt = (
        select(Scenario)
        .where(Scenario.user_id == principal.id)
        .order_by(Scenario.created_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


@router.post("", response_model=ScenarioOut, status_code=status.HTTP_201_CREATED)
async def create_scenario(
    payload: ScenarioIn,
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Scenario:
    row = Scenario(
        user_id=principal.id,
        name=payload.name,
        description=payload.description,
        cbot_soja_shock_pct=payload.cbot_soja_shock_pct,
        cbot_milho_shock_pct=payload.cbot_milho_shock_pct,
        basis_soja_shock_pct=payload.basis_soja_shock_pct,
        basis_milho_shock_pct=payload.basis_milho_shock_pct,
        fx_shock_pct=payload.fx_shock_pct,
        is_historical=payload.is_historical,
        source_period=payload.source_period,
    )
    session.add(row)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=_detail("scenario name already exists", {"name": payload.name}),
        ) from exc
    await session.refresh(row)
    return row


@router.get("/{scenario_id}", response_model=ScenarioOut)
async def get_scenario(
    scenario_id: UUID,
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Scenario:
    row = (
        await session.execute(
            select(Scenario).where(Scenario.id == scenario_id, Scenario.user_id == principal.id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_detail("scenario not found"))
    return row


@router.patch("/{scenario_id}", response_model=ScenarioOut)
async def update_scenario(
    scenario_id: UUID,
    update: ScenarioUpdate,
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Scenario:
    row = (
        await session.execute(
            select(Scenario).where(Scenario.id == scenario_id, Scenario.user_id == principal.id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_detail("scenario not found"))
    for k, v in update.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=_detail("scenario name already exists"),
        ) from exc
    await session.refresh(row)
    return row


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scenario(
    scenario_id: UUID,
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    row = (
        await session.execute(
            select(Scenario).where(Scenario.id == scenario_id, Scenario.user_id == principal.id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_detail("scenario not found"))
    await session.delete(row)
    await session.commit()
