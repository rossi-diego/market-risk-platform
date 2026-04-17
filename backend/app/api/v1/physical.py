"""Physical contracts: frames (parent) + fixations (partial pricing events).

Over-fix protection, atomic fixation insert + status recompute + audit log.
All endpoints require a valid Supabase JWT.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_session
from app.core.security import UserPrincipal, get_current_user
from app.models.enums import PositionStatus
from app.models.physical import PhysicalFixation, PhysicalFrame
from app.risk.exposure import open_exposure_frame
from app.risk.types import DomainError
from app.schemas.physical import (
    PhysicalFixationIn,
    PhysicalFixationOut,
    PhysicalFrameDetailOut,
    PhysicalFrameIn,
    PhysicalFrameOut,
    PhysicalFrameUpdate,
    PhysicalFrameWithExposureOut,
)
from app.services.events import log_trade_event
from app.services.status_recompute import recompute_frame_status

router = APIRouter(prefix="/physical", tags=["physical"])

_ALLOWED_PATCH_FIELDS = {"counterparty", "notes", "status"}


def _detail(title: str, extra: dict[str, object] | None = None) -> dict[str, object]:
    body: dict[str, object] = {"type": "about:blank", "title": title}
    if extra:
        body.update(extra)
    return body


async def _get_owned_frame(session: AsyncSession, frame_id: UUID, user_id: UUID) -> PhysicalFrame:
    result = await session.execute(
        select(PhysicalFrame).where(PhysicalFrame.id == frame_id, PhysicalFrame.user_id == user_id)
    )
    frame = result.scalar_one_or_none()
    if frame is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_detail("frame not found"))
    return frame


def _to_exposure_out(
    frame: PhysicalFrame, fixations: list[PhysicalFixation]
) -> PhysicalFrameWithExposureOut:
    fe = open_exposure_frame(frame, fixations)
    return PhysicalFrameWithExposureOut(
        id=frame.id,
        user_id=frame.user_id,
        commodity=frame.commodity.value,
        side=frame.side.value,
        quantity_tons=frame.quantity_tons,
        delivery_start=frame.delivery_start,
        delivery_end=frame.delivery_end,
        counterparty=frame.counterparty,
        status=frame.status.value,
        notes=frame.notes,
        created_at=frame.created_at,
        updated_at=frame.updated_at,
        open_cbot_tons=fe.open.cbot_qty_tons,
        open_basis_tons=fe.open.basis_qty_tons,
        open_fx_tons=fe.open.fx_qty_tons,
        locked_cbot_tons=fe.locked.cbot_qty_tons,
        locked_basis_tons=fe.locked.basis_qty_tons,
        locked_fx_tons=fe.locked.fx_qty_tons,
    )


@router.get("/frames", response_model=list[PhysicalFrameWithExposureOut])
async def list_frames(
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status_filter: PositionStatus | None = Query(None, alias="status"),
) -> list[PhysicalFrameWithExposureOut]:
    stmt = (
        select(PhysicalFrame)
        .where(PhysicalFrame.user_id == principal.id)
        .options(selectinload(PhysicalFrame.fixations))
        .order_by(PhysicalFrame.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status_filter is not None:
        stmt = stmt.where(PhysicalFrame.status == status_filter)
    frames = list((await session.execute(stmt)).scalars().all())
    return [_to_exposure_out(f, list(f.fixations)) for f in frames]


@router.post(
    "/frames",
    response_model=PhysicalFrameOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_frame(
    payload: PhysicalFrameIn,
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PhysicalFrame:
    frame = PhysicalFrame(
        user_id=principal.id,
        commodity=payload.commodity,
        side=payload.side,
        quantity_tons=payload.quantity_tons,
        delivery_start=payload.delivery_start,
        delivery_end=payload.delivery_end,
        counterparty=payload.counterparty,
        notes=payload.notes,
        status=PositionStatus.OPEN,
    )
    session.add(frame)
    await session.flush()
    await log_trade_event(
        session,
        user_id=principal.id,
        event_type="open",
        instrument_table="physical_frames",
        instrument_id=frame.id,
        quantity=frame.quantity_tons,
        payload={"commodity": frame.commodity.value, "side": frame.side.value},
    )
    await session.commit()
    await session.refresh(frame)
    return frame


@router.get("/frames/{frame_id}", response_model=PhysicalFrameDetailOut)
async def get_frame(
    frame_id: UUID,
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PhysicalFrame:
    stmt = (
        select(PhysicalFrame)
        .where(PhysicalFrame.id == frame_id, PhysicalFrame.user_id == principal.id)
        .options(selectinload(PhysicalFrame.fixations))
    )
    frame = (await session.execute(stmt)).scalar_one_or_none()
    if frame is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_detail("frame not found"))
    return frame


@router.patch("/frames/{frame_id}", response_model=PhysicalFrameOut)
async def update_frame(
    frame_id: UUID,
    update: PhysicalFrameUpdate,
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PhysicalFrame:
    frame = await _get_owned_frame(session, frame_id, principal.id)
    patch = update.model_dump(exclude_unset=True)
    invalid = set(patch.keys()) - _ALLOWED_PATCH_FIELDS
    if invalid:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=_detail("unpatchable fields", {"fields": sorted(invalid)}),
        )
    for k, v in patch.items():
        setattr(frame, k, v)
    await session.commit()
    await session.refresh(frame)
    return frame


@router.delete("/frames/{frame_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_frame(
    frame_id: UUID,
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    cascade: bool = Query(False),
) -> None:
    frame = await _get_owned_frame(session, frame_id, principal.id)
    fixations_count = (
        await session.execute(select(PhysicalFixation).where(PhysicalFixation.frame_id == frame.id))
    ).all()
    if fixations_count and not cascade:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=_detail(
                "frame has fixations",
                {"fixations_count": len(fixations_count), "hint": "pass ?cascade=true"},
            ),
        )
    await session.delete(frame)
    await session.commit()


@router.post(
    "/frames/{frame_id}/fixations",
    response_model=PhysicalFixationOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_fixation(
    frame_id: UUID,
    payload: PhysicalFixationIn,
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PhysicalFixation:
    stmt = (
        select(PhysicalFrame)
        .where(PhysicalFrame.id == frame_id, PhysicalFrame.user_id == principal.id)
        .options(selectinload(PhysicalFrame.fixations))
    )
    frame = (await session.execute(stmt)).scalar_one_or_none()
    if frame is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_detail("frame not found"))

    tentative = PhysicalFixation(
        frame_id=frame.id,
        fixation_mode=payload.fixation_mode,
        quantity_tons=payload.quantity_tons,
        fixation_date=payload.fixation_date,
        cbot_fixed=payload.cbot_fixed,
        basis_fixed=payload.basis_fixed,
        fx_fixed=payload.fx_fixed,
        reference_cbot_contract=payload.reference_cbot_contract,
        notes=payload.notes,
    )
    try:
        open_exposure_frame(frame, [*frame.fixations, tentative])
    except DomainError as exc:
        msg = str(exc)
        leg = msg.split("leg ")[1].split(":")[0] if "leg " in msg else "unknown"
        fe = open_exposure_frame(frame, list(frame.fixations))
        remaining_map = {
            "cbot": fe.open.cbot_qty_tons,
            "basis": fe.open.basis_qty_tons,
            "fx": fe.open.fx_qty_tons,
        }
        remaining = remaining_map.get(leg)
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=_detail(
                "over-locked leg",
                {"leg": leg, "remaining_tons": str(remaining) if remaining is not None else None},
            ),
        ) from exc

    session.add(tentative)
    await session.flush()
    await recompute_frame_status(session, frame)
    await log_trade_event(
        session,
        user_id=principal.id,
        event_type="fill",
        instrument_table="physical_frames",
        instrument_id=frame.id,
        quantity=tentative.quantity_tons,
        payload={
            "fixation_id": str(tentative.id),
            "mode": tentative.fixation_mode.value,
            "qty": str(tentative.quantity_tons),
        },
    )
    await session.commit()
    await session.refresh(tentative)
    return tentative


@router.delete("/fixations/{fixation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fixation(
    fixation_id: UUID,
    principal: Annotated[UserPrincipal, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    stmt = (
        select(PhysicalFixation, PhysicalFrame)
        .join(PhysicalFrame, PhysicalFrame.id == PhysicalFixation.frame_id)
        .where(PhysicalFixation.id == fixation_id, PhysicalFrame.user_id == principal.id)
    )
    row = (await session.execute(stmt)).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_detail("fixation not found"))
    fixation, frame = row
    await session.delete(fixation)
    await session.flush()
    await recompute_frame_status(session, frame)
    await log_trade_event(
        session,
        user_id=principal.id,
        event_type="adjust",
        instrument_table="physical_frames",
        instrument_id=frame.id,
        quantity=fixation.quantity_tons,
        payload={"deleted_fixation_id": str(fixation.id)},
    )
    await session.commit()
