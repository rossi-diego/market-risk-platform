import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, pg_enum
from app.models.enums import Commodity, PositionStatus, Side


class BasisForward(Base, TimestampMixin):
    __tablename__ = "basis_forwards"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    commodity: Mapped[Commodity] = mapped_column(pg_enum(Commodity, "commodity"), nullable=False)
    side: Mapped[Side] = mapped_column(pg_enum(Side, "side"), nullable=False)
    quantity_tons: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    basis_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    reference_cbot_contract: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[PositionStatus] = mapped_column(
        pg_enum(PositionStatus, "position_status"),
        nullable=False,
        server_default="open",
    )
    counterparty: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
