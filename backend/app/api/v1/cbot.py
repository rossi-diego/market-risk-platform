"""CBOT derivatives CRUD (futures, swaps, options, barrier options)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import UserPrincipal, get_current_user
from app.models.cbot import CBOTDerivative
from app.models.enums import CBOTInstrument, PositionStatus
from app.schemas.cbot import (
    CBOTDerivativeIn,
    CBOTDerivativeOut,
    CBOTDerivativeUpdate,
)
from app.services.events import log_trade_event

router = APIRouter(prefix="/cbot", tags=["cbot"])

_OPTION_INSTRUMENTS = {
    CBOTInstrument.EUROPEAN_OPTION,
    CBOTInstrument.AMERICAN_OPTION,
    CBOTInstrument.BARRIER_OPTION,
}


def _detail(title: str, extra: dict[str, object] | None = None) -> dict[str, object]:
    body: dict[str, object] = {"type": "about:blank", "title": title}
    if extra:
        body.update(extra)
    return body


def _validate_option_fields(payload: CBOTDerivativeIn) -> None:
    is_option = payload.instrument in _OPTION_INSTRUMENTS
    if is_option and (payload.option_type is None or payload.strike is None):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_detail(
                "option_type and strike required for option instruments",
                {"instrument": payload.instrument},
            ),
        )
    if payload.instrument == CBOTInstrument.BARRIER_OPTION.value and (
        payload.barrier_type is None or payload.barrier_level is None
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_detail("barrier_type and barrier_level required for barrier_option"),
        )


@router.get("", response_model=list[CBOTDerivativeOut])
async def list_cbot(
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status_filter: PositionStatus | None = Query(None, alias="status"),
) -> list[CBOTDerivative]:
    stmt = (
        select(CBOTDerivative)
        .where(CBOTDerivative.user_id == principal.id)
        .order_by(CBOTDerivative.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status_filter is not None:
        stmt = stmt.where(CBOTDerivative.status == status_filter)
    return list((await session.execute(stmt)).scalars().all())


@router.post("", response_model=CBOTDerivativeOut, status_code=status.HTTP_201_CREATED)
async def create_cbot(
    payload: CBOTDerivativeIn,
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CBOTDerivative:
    _validate_option_fields(payload)
    row = CBOTDerivative(
        user_id=principal.id,
        commodity=payload.commodity,
        instrument=payload.instrument,
        side=payload.side,
        contract=payload.contract,
        quantity_contracts=payload.quantity_contracts,
        trade_date=payload.trade_date,
        trade_price=payload.trade_price,
        maturity_date=payload.maturity_date,
        option_type=payload.option_type,
        strike=payload.strike,
        barrier_type=payload.barrier_type,
        barrier_level=payload.barrier_level,
        rebate=payload.rebate,
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
        instrument_table="cbot_derivatives",
        instrument_id=row.id,
        quantity=row.quantity_contracts,
        price=row.trade_price,
        payload={"instrument": row.instrument.value, "side": row.side.value},
    )
    await session.commit()
    await session.refresh(row)
    return row


@router.get("/{row_id}", response_model=CBOTDerivativeOut)
async def get_cbot(
    row_id: UUID,
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CBOTDerivative:
    row = (
        await session.execute(
            select(CBOTDerivative).where(
                CBOTDerivative.id == row_id, CBOTDerivative.user_id == principal.id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_detail("cbot derivative not found"))
    return row


@router.patch("/{row_id}", response_model=CBOTDerivativeOut)
async def update_cbot(
    row_id: UUID,
    update: CBOTDerivativeUpdate,
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CBOTDerivative:
    row = (
        await session.execute(
            select(CBOTDerivative).where(
                CBOTDerivative.id == row_id, CBOTDerivative.user_id == principal.id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_detail("cbot derivative not found"))
    for k, v in update.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    await session.commit()
    await session.refresh(row)
    return row


@router.delete("/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cbot(
    row_id: UUID,
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    row = (
        await session.execute(
            select(CBOTDerivative).where(
                CBOTDerivative.id == row_id, CBOTDerivative.user_id == principal.id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_detail("cbot derivative not found"))
    await session.delete(row)
    await log_trade_event(
        session,
        user_id=principal.id,
        event_type="close",
        instrument_table="cbot_derivatives",
        instrument_id=row.id,
        quantity=row.quantity_contracts,
    )
    await session.commit()
