from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TradeEventIn(BaseModel):
    event_type: str
    instrument_table: str
    instrument_id: UUID
    quantity: Decimal | None = None
    price: Decimal | None = None
    event_date: datetime | None = None
    payload: dict[str, Any] | None = None


class TradeEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    event_type: str
    instrument_table: str
    instrument_id: UUID
    quantity: Decimal | None
    price: Decimal | None
    event_date: datetime
    payload: dict[str, Any] | None
    created_at: datetime


class TradeEventUpdate(BaseModel):
    event_type: str | None = None
    instrument_table: str | None = None
    instrument_id: UUID | None = None
    quantity: Decimal | None = None
    price: Decimal | None = None
    event_date: datetime | None = None
    payload: dict[str, Any] | None = None
