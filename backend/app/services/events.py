"""Helpers for writing rows into the polymorphic `trade_events` audit log."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.events import TradeEvent


async def log_trade_event(
    session: AsyncSession,
    *,
    user_id: UUID,
    event_type: str,
    instrument_table: str,
    instrument_id: UUID,
    quantity: Decimal | None = None,
    price: Decimal | None = None,
    payload: dict[str, Any] | None = None,
) -> TradeEvent:
    event = TradeEvent(
        user_id=user_id,
        event_type=event_type,
        instrument_table=instrument_table,
        instrument_id=instrument_id,
        quantity=quantity,
        price=price,
        payload=payload,
    )
    session.add(event)
    await session.flush()
    return event
