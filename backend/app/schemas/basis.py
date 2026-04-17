from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.common import LiteralCommodity, LiteralPositionStatus, LiteralSide


class BasisForwardIn(BaseModel):
    commodity: LiteralCommodity
    side: LiteralSide
    quantity_tons: Decimal
    trade_date: date
    basis_price: Decimal
    delivery_date: date
    reference_cbot_contract: str
    counterparty: str | None = None
    notes: str | None = None


class BasisForwardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    commodity: LiteralCommodity
    side: LiteralSide
    quantity_tons: Decimal
    trade_date: date
    basis_price: Decimal
    delivery_date: date
    reference_cbot_contract: str
    status: LiteralPositionStatus
    counterparty: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class BasisForwardUpdate(BaseModel):
    commodity: LiteralCommodity | None = None
    side: LiteralSide | None = None
    quantity_tons: Decimal | None = None
    trade_date: date | None = None
    basis_price: Decimal | None = None
    delivery_date: date | None = None
    reference_cbot_contract: str | None = None
    status: LiteralPositionStatus | None = None
    counterparty: str | None = None
    notes: str | None = None
