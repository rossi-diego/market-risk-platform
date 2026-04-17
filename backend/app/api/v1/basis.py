"""Basis forwards CRUD."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import UserPrincipal, get_current_user
from app.models.basis import BasisForward
from app.models.enums import PositionStatus
from app.schemas.basis import BasisForwardIn, BasisForwardOut, BasisForwardUpdate
from app.services.events import log_trade_event

router = APIRouter(prefix="/basis", tags=["basis"])


def _detail(title: str) -> dict[str, object]:
    return {"type": "about:blank", "title": title}


@router.get("", response_model=list[BasisForwardOut])
async def list_basis(
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status_filter: PositionStatus | None = Query(None, alias="status"),
) -> list[BasisForward]:
    stmt = (
        select(BasisForward)
        .where(BasisForward.user_id == principal.id)
        .order_by(BasisForward.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status_filter is not None:
        stmt = stmt.where(BasisForward.status == status_filter)
    return list((await session.execute(stmt)).scalars().all())


@router.post("", response_model=BasisForwardOut, status_code=status.HTTP_201_CREATED)
async def create_basis(
    payload: BasisForwardIn,
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BasisForward:
    row = BasisForward(
        user_id=principal.id,
        commodity=payload.commodity,
        side=payload.side,
        quantity_tons=payload.quantity_tons,
        trade_date=payload.trade_date,
        basis_price=payload.basis_price,
        delivery_date=payload.delivery_date,
        reference_cbot_contract=payload.reference_cbot_contract,
        counterparty=payload.counterparty,
        notes=payload.notes,
        status=PositionStatus.OPEN,
    )
    session.add(row)
    await session.flush()
    await log_trade_event(
        session,
        user_id=principal.id,
        event_type="open",
        instrument_table="basis_forwards",
        instrument_id=row.id,
        quantity=row.quantity_tons,
        price=row.basis_price,
    )
    await session.commit()
    await session.refresh(row)
    return row


@router.get("/{row_id}", response_model=BasisForwardOut)
async def get_basis(
    row_id: UUID,
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BasisForward:
    row = (
        await session.execute(
            select(BasisForward).where(
                BasisForward.id == row_id, BasisForward.user_id == principal.id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_detail("basis forward not found"))
    return row


@router.patch("/{row_id}", response_model=BasisForwardOut)
async def update_basis(
    row_id: UUID,
    update: BasisForwardUpdate,
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BasisForward:
    row = (
        await session.execute(
            select(BasisForward).where(
                BasisForward.id == row_id, BasisForward.user_id == principal.id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_detail("basis forward not found"))
    for k, v in update.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    await session.commit()
    await session.refresh(row)
    return row


@router.delete("/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_basis(
    row_id: UUID,
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    row = (
        await session.execute(
            select(BasisForward).where(
                BasisForward.id == row_id, BasisForward.user_id == principal.id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_detail("basis forward not found"))
    await session.delete(row)
    await log_trade_event(
        session,
        user_id=principal.id,
        event_type="close",
        instrument_table="basis_forwards",
        instrument_id=row.id,
        quantity=row.quantity_tons,
    )
    await session.commit()
