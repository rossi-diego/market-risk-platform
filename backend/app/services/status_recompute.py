"""Derive `physical_frames.status` from the set of fixations attached to it.

Rules (CLAUDE.md > Fixation Modes):
  - 0 fixations               → "open"
  - any leg with locked < total → "partial"
  - all 3 legs fully locked   → "closed"
  - delivery_end in the past  → "expired" (handled by a separate cron)
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import FixationMode, PositionStatus
from app.models.physical import PhysicalFixation, PhysicalFrame

_CBOT_LOCKING = {FixationMode.FLAT, FixationMode.CBOT, FixationMode.CBOT_BASIS}
_BASIS_LOCKING = {FixationMode.FLAT, FixationMode.CBOT_BASIS, FixationMode.BASIS}
_FX_LOCKING = {FixationMode.FLAT, FixationMode.FX}


async def recompute_frame_status(session: AsyncSession, frame: PhysicalFrame) -> PositionStatus:
    result = await session.execute(
        select(PhysicalFixation).where(PhysicalFixation.frame_id == frame.id)
    )
    fixations = list(result.scalars().all())

    if not fixations:
        new_status = PositionStatus.OPEN
    else:
        locked_cbot = Decimal(0)
        locked_basis = Decimal(0)
        locked_fx = Decimal(0)
        for f in fixations:
            if f.fixation_mode in _CBOT_LOCKING:
                locked_cbot += f.quantity_tons
            if f.fixation_mode in _BASIS_LOCKING:
                locked_basis += f.quantity_tons
            if f.fixation_mode in _FX_LOCKING:
                locked_fx += f.quantity_tons
        total = frame.quantity_tons
        if locked_cbot >= total and locked_basis >= total and locked_fx >= total:
            new_status = PositionStatus.CLOSED
        else:
            new_status = PositionStatus.PARTIAL

    frame.status = new_status
    await session.flush()
    return new_status
