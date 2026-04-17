from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.common import (
    LiteralBarrierType,
    LiteralFXInstrument,
    LiteralOptionType,
    LiteralPositionStatus,
    LiteralSide,
)


class FXDerivativeIn(BaseModel):
    instrument: LiteralFXInstrument
    side: LiteralSide
    notional_usd: Decimal
    trade_date: date
    trade_rate: Decimal
    maturity_date: date
    option_type: LiteralOptionType | None = None
    strike: Decimal | None = None
    barrier_type: LiteralBarrierType | None = None
    barrier_level: Decimal | None = None
    rebate: Decimal | None = None
    counterparty: str | None = None
    notes: str | None = None


class FXDerivativeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    instrument: LiteralFXInstrument
    side: LiteralSide
    notional_usd: Decimal
    trade_date: date
    trade_rate: Decimal
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


class FXDerivativeUpdate(BaseModel):
    instrument: LiteralFXInstrument | None = None
    side: LiteralSide | None = None
    notional_usd: Decimal | None = None
    trade_date: date | None = None
    trade_rate: Decimal | None = None
    maturity_date: date | None = None
    option_type: LiteralOptionType | None = None
    strike: Decimal | None = None
    barrier_type: LiteralBarrierType | None = None
    barrier_level: Decimal | None = None
    rebate: Decimal | None = None
    status: LiteralPositionStatus | None = None
    counterparty: str | None = None
    notes: str | None = None
