import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, pg_enum
from app.models.enums import Commodity


class MTMPremium(Base):
    __tablename__ = "mtm_premiums"

    commodity: Mapped[Commodity] = mapped_column(pg_enum(Commodity, "commodity"), primary_key=True)
    premium_usd_bu: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class ScenarioTemplate(Base):
    __tablename__ = "scenarios_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    cbot_soja_shock_pct: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), nullable=False, server_default="0"
    )
    cbot_milho_shock_pct: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), nullable=False, server_default="0"
    )
    basis_soja_shock_pct: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), nullable=False, server_default="0"
    )
    basis_milho_shock_pct: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), nullable=False, server_default="0"
    )
    fx_shock_pct: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False, server_default="0")
    source_period: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Scenario(Base):
    __tablename__ = "scenarios"
    __table_args__ = (UniqueConstraint("user_id", "name", name="scenarios_user_id_name_key"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    cbot_soja_shock_pct: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), nullable=False, server_default="0"
    )
    cbot_milho_shock_pct: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), nullable=False, server_default="0"
    )
    basis_soja_shock_pct: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), nullable=False, server_default="0"
    )
    basis_milho_shock_pct: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), nullable=False, server_default="0"
    )
    fx_shock_pct: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False, server_default="0")
    is_historical: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    source_period: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
