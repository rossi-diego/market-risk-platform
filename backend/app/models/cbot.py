import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import (
    BarrierType,
    CBOTInstrument,
    Commodity,
    OptionType,
    PositionStatus,
    Side,
)


class CBOTDerivative(Base, TimestampMixin):
    __tablename__ = "cbot_derivatives"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    commodity: Mapped[Commodity] = mapped_column(
        Enum(Commodity, name="commodity", native_enum=True, create_type=False), nullable=False
    )
    instrument: Mapped[CBOTInstrument] = mapped_column(
        Enum(CBOTInstrument, name="cbot_instrument", native_enum=True, create_type=False),
        nullable=False,
    )
    side: Mapped[Side] = mapped_column(
        Enum(Side, name="side", native_enum=True, create_type=False), nullable=False
    )
    contract: Mapped[str] = mapped_column(String, nullable=False)
    quantity_contracts: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    trade_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    maturity_date: Mapped[date] = mapped_column(Date, nullable=False)
    option_type: Mapped[OptionType | None] = mapped_column(
        Enum(OptionType, name="option_type", native_enum=True, create_type=False), nullable=True
    )
    strike: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    barrier_type: Mapped[BarrierType | None] = mapped_column(
        Enum(BarrierType, name="barrier_type", native_enum=True, create_type=False), nullable=True
    )
    barrier_level: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    rebate: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    status: Mapped[PositionStatus] = mapped_column(
        Enum(PositionStatus, name="position_status", native_enum=True, create_type=False),
        nullable=False,
        server_default="open",
    )
    counterparty: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
