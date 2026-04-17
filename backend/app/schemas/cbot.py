from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.common import (
    LiteralBarrierType,
    LiteralCBOTInstrument,
    LiteralCommodity,
    LiteralOptionType,
    LiteralPositionStatus,
    LiteralSide,
)


class CBOTDerivativeIn(BaseModel):
    commodity: LiteralCommodity
    instrument: LiteralCBOTInstrument
    side: LiteralSide
    contract: str
    quantity_contracts: Decimal
    trade_date: date
    trade_price: Decimal
    maturity_date: date
    option_type: LiteralOptionType | None = None
    strike: Decimal | None = None
    barrier_type: LiteralBarrierType | None = None
    barrier_level: Decimal | None = None
    rebate: Decimal | None = None
    counterparty: str | None = None
    notes: str | None = None


class CBOTDerivativeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    commodity: LiteralCommodity
    instrument: LiteralCBOTInstrument
    side: LiteralSide
    contract: str
    quantity_contracts: Decimal
    trade_date: date
    trade_price: Decimal
    maturity_date: date
    option_type: LiteralOptionType | None
    strike: Decimal | None
    barrier_type: LiteralBarrierType | None
    barrier_level: Decimal | None
    rebate: Decimal | None
    status: LiteralPositionStatus
    counterparty: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class CBOTDerivativeUpdate(BaseModel):
    commodity: LiteralCommodity | None = None
    instrument: LiteralCBOTInstrument | None = None
    side: LiteralSide | None = None
    contract: str | None = None
    quantity_contracts: Decimal | None = None
    trade_date: date | None = None
    trade_price: Decimal | None = None
    maturity_date: date | None = None
    option_type: LiteralOptionType | None = None
    strike: Decimal | None = None
    barrier_type: LiteralBarrierType | None = None
    barrier_level: Decimal | None = None
    rebate: Decimal | None = None
    status: LiteralPositionStatus | None = None
    counterparty: str | None = None
    notes: str | None = None
