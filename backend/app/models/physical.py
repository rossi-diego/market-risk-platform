import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, pg_enum
from app.models.enums import Commodity, FixationMode, PositionStatus, Side


class PhysicalFrame(Base, TimestampMixin):
    __tablename__ = "physical_frames"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    commodity: Mapped[Commodity] = mapped_column(pg_enum(Commodity, "commodity"), nullable=False)
    side: Mapped[Side] = mapped_column(pg_enum(Side, "side"), nullable=False)
    quantity_tons: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    delivery_start: Mapped[date] = mapped_column(Date, nullable=False)
    delivery_end: Mapped[date] = mapped_column(Date, nullable=False)
    counterparty: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[PositionStatus] = mapped_column(
        pg_enum(PositionStatus, "position_status"),
        nullable=False,
        server_default="open",
    )
    notes: Mapped[str | None] = mapped_column(String, nullable=True)

    fixations: Mapped[list["PhysicalFixation"]] = relationship(
        back_populates="frame", cascade="all, delete-orphan"
    )


class PhysicalFixation(Base):
    __tablename__ = "physical_fixations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    frame_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("physical_frames.id", ondelete="CASCADE"),
        nullable=False,
    )
    fixation_mode: Mapped[FixationMode] = mapped_column(
        pg_enum(FixationMode, "fixation_mode"), nullable=False
    )
    quantity_tons: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    fixation_date: Mapped[date] = mapped_column(Date, nullable=False)
    cbot_fixed: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    basis_fixed: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    fx_fixed: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    reference_cbot_contract: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    frame: Mapped["PhysicalFrame"] = relationship(back_populates="fixations")
