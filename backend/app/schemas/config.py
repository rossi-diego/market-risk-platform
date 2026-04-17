from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.common import LiteralCommodity


class MTMPremiumIn(BaseModel):
    commodity: LiteralCommodity
    premium_usd_bu: Decimal


class MTMPremiumOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    commodity: LiteralCommodity
    premium_usd_bu: Decimal
    updated_at: datetime
    updated_by: UUID | None


class MTMPremiumUpdate(BaseModel):
    premium_usd_bu: Decimal | None = None


class ScenarioTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    cbot_soja_shock_pct: Decimal
    cbot_milho_shock_pct: Decimal
    basis_soja_shock_pct: Decimal
    basis_milho_shock_pct: Decimal
    fx_shock_pct: Decimal
    source_period: str | None
    created_at: datetime


class ScenarioIn(BaseModel):
    name: str
    description: str | None = None
    cbot_soja_shock_pct: Decimal = Decimal("0")
    cbot_milho_shock_pct: Decimal = Decimal("0")
    basis_soja_shock_pct: Decimal = Decimal("0")
    basis_milho_shock_pct: Decimal = Decimal("0")
    fx_shock_pct: Decimal = Decimal("0")
    is_historical: bool = False
    source_period: str | None = None


class ScenarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    name: str
    description: str | None
    cbot_soja_shock_pct: Decimal
    cbot_milho_shock_pct: Decimal
    basis_soja_shock_pct: Decimal
    basis_milho_shock_pct: Decimal
    fx_shock_pct: Decimal
    is_historical: bool
    source_period: str | None
    created_at: datetime


class ScenarioUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    cbot_soja_shock_pct: Decimal | None = None
    cbot_milho_shock_pct: Decimal | None = None
    basis_soja_shock_pct: Decimal | None = None
    basis_milho_shock_pct: Decimal | None = None
    fx_shock_pct: Decimal | None = None
    is_historical: bool | None = None
    source_period: str | None = None
