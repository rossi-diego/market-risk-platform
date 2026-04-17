"""Domain value types for the risk engine.

`LegExposure` carries *non-negative* per-leg tonnages — used for the
`open`/`locked` fields of a single frame where negative values are
nonsensical by construction.

`SignedLegExposure` is the same shape without the non-negativity
invariant, used by `AggregateExposure` where buy=+1 / sell=-1 nets
can legitimately go negative when shorts dominate longs on a leg.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from app.models.enums import Commodity, Side


class DomainError(Exception):
    """Raised when a domain invariant is violated (e.g. over-locked leg)."""


@dataclass(frozen=True, slots=True)
class LegExposure:
    cbot_qty_tons: Decimal
    basis_qty_tons: Decimal
    fx_qty_tons: Decimal

    def __post_init__(self) -> None:
        for name, value in (
            ("cbot_qty_tons", self.cbot_qty_tons),
            ("basis_qty_tons", self.basis_qty_tons),
            ("fx_qty_tons", self.fx_qty_tons),
        ):
            if value < 0:
                raise ValueError(f"{name} must be >= 0, got {value}")


@dataclass(frozen=True, slots=True)
class SignedLegExposure:
    cbot_qty_tons: Decimal
    basis_qty_tons: Decimal
    fx_qty_tons: Decimal


@dataclass(frozen=True, slots=True)
class FrameExposure:
    frame_id: UUID
    commodity: Commodity
    side: Side
    total_tons: Decimal
    open: LegExposure
    locked: LegExposure


@dataclass(frozen=True, slots=True)
class AggregateExposure:
    by_commodity: dict[Commodity, SignedLegExposure] = field(default_factory=dict)
    total: SignedLegExposure = field(
        default_factory=lambda: SignedLegExposure(
            cbot_qty_tons=Decimal(0),
            basis_qty_tons=Decimal(0),
            fx_qty_tons=Decimal(0),
        )
    )
    fx_notional_usd: Decimal = Decimal(0)
