from datetime import date, datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from app.schemas.common import (
    LiteralCommodity,
    LiteralFixationMode,
    LiteralPositionStatus,
    LiteralSide,
)

# Which legs each fixation mode locks. Used by the validator below
# to mirror the DB CHECK constraint on physical_fixations.
_MODE_LEG_MAP: dict[str, dict[str, bool]] = {
    "flat": {"cbot": True, "basis": True, "fx": True},
    "cbot": {"cbot": True, "basis": False, "fx": False},
    "cbot_basis": {"cbot": True, "basis": True, "fx": False},
    "basis": {"cbot": False, "basis": True, "fx": False},
    "fx": {"cbot": False, "basis": False, "fx": True},
}


class PhysicalFrameIn(BaseModel):
    commodity: LiteralCommodity
    side: LiteralSide
    quantity_tons: Decimal
    delivery_start: date
    delivery_end: date
    counterparty: str | None = None
    notes: str | None = None


class PhysicalFrameOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    commodity: LiteralCommodity
    side: LiteralSide
    quantity_tons: Decimal
    delivery_start: date
    delivery_end: date
    counterparty: str | None
    status: LiteralPositionStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime


class PhysicalFrameUpdate(BaseModel):
    commodity: LiteralCommodity | None = None
    side: LiteralSide | None = None
    quantity_tons: Decimal | None = None
    delivery_start: date | None = None
    delivery_end: date | None = None
    counterparty: str | None = None
    status: LiteralPositionStatus | None = None
    notes: str | None = None


class PhysicalFixationIn(BaseModel):
    fixation_mode: LiteralFixationMode
    quantity_tons: Decimal
    fixation_date: date
    cbot_fixed: Decimal | None = None
    basis_fixed: Decimal | None = None
    fx_fixed: Decimal | None = None
    reference_cbot_contract: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _enforce_mode_leg_constraint(self) -> Self:
        expected = _MODE_LEG_MAP[self.fixation_mode]
        supplied = {
            "cbot": self.cbot_fixed is not None,
            "basis": self.basis_fixed is not None,
            "fx": self.fx_fixed is not None,
        }
        mismatches = [leg for leg, must in expected.items() if supplied[leg] != must]
        if mismatches:
            required_legs = sorted(leg for leg, must in expected.items() if must)
            raise ValueError(
                f"fixation_mode={self.fixation_mode!r} requires exactly "
                f"{required_legs} leg(s) to be set (got mismatch on: {mismatches})"
            )
        return self


class PhysicalFixationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    frame_id: UUID
    fixation_mode: LiteralFixationMode
    quantity_tons: Decimal
    fixation_date: date
    cbot_fixed: Decimal | None
    basis_fixed: Decimal | None
    fx_fixed: Decimal | None
    reference_cbot_contract: str | None
    notes: str | None
    created_at: datetime


class PhysicalFixationUpdate(BaseModel):
    fixation_mode: LiteralFixationMode | None = None
    quantity_tons: Decimal | None = None
    fixation_date: date | None = None
    cbot_fixed: Decimal | None = None
    basis_fixed: Decimal | None = None
    fx_fixed: Decimal | None = None
    reference_cbot_contract: str | None = None
    notes: str | None = None


class PhysicalFrameDetailOut(PhysicalFrameOut):
    fixations: list[PhysicalFixationOut] = []
