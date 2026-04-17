from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.common import LiteralCommodity, LiteralPriceSource


class PriceIn(BaseModel):
    observed_at: datetime
    instrument: str
    commodity: LiteralCommodity | None = None
    value: Decimal
    unit: str
    price_source: LiteralPriceSource


class PriceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    observed_at: datetime
    instrument: str
    commodity: LiteralCommodity | None
    value: Decimal
    unit: str
    price_source: LiteralPriceSource
    created_at: datetime


class PriceUpdate(BaseModel):
    observed_at: datetime | None = None
    instrument: str | None = None
    commodity: LiteralCommodity | None = None
    value: Decimal | None = None
    unit: str | None = None
    price_source: LiteralPriceSource | None = None
