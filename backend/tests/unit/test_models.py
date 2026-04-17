"""Unit tests for ORM models + Pydantic schemas.

Scope: pure Python (no DB roundtrip). DB integration tests live in Phase 5.
Each test exercises instantiation, enum coercion, Decimal round-trip, and the
Pydantic validators that mirror DB CHECK constraints.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models import (
    BasisForward,
    CBOTDerivative,
    CBOTInstrument,
    Commodity,
    FixationMode,
    FXDerivative,
    FXInstrument,
    MTMPremium,
    PhysicalFixation,
    PhysicalFrame,
    Price,
    PriceSource,
    Scenario,
    ScenarioTemplate,
    Side,
    TradeEvent,
)
from app.schemas import (
    BasisForwardIn,
    CBOTDerivativeIn,
    FXDerivativeIn,
    PhysicalFixationIn,
    PhysicalFrameIn,
    PriceIn,
)

# ---------------------------------------------------------------------------
# Tablename invariants — every family must land on the expected Postgres table
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        (Price, "prices"),
        (PhysicalFrame, "physical_frames"),
        (PhysicalFixation, "physical_fixations"),
        (CBOTDerivative, "cbot_derivatives"),
        (BasisForward, "basis_forwards"),
        (FXDerivative, "fx_derivatives"),
        (TradeEvent, "trade_events"),
        (MTMPremium, "mtm_premiums"),
        (Scenario, "scenarios"),
        (ScenarioTemplate, "scenarios_templates"),
    ],
)
def test_model_tablename(model: type, expected: str) -> None:
    assert model.__tablename__ == expected


# ---------------------------------------------------------------------------
# Model instantiation + enum coercion + Decimal round-trip
# ---------------------------------------------------------------------------


def test_price_instantiation() -> None:
    p = Price(
        observed_at=datetime(2026, 4, 15, tzinfo=UTC),
        instrument="ZS=F",
        commodity=Commodity.SOJA,
        value=Decimal("1423.75"),
        unit="USc/bu",
        price_source=PriceSource.YFINANCE_CBOT,
    )
    assert p.commodity == Commodity.SOJA
    assert p.commodity == "soja"  # StrEnum identity
    assert p.value == Decimal("1423.75")
    assert p.price_source == PriceSource.YFINANCE_CBOT


def test_physical_frame_instantiation_and_enum_str_coercion() -> None:
    # Passing a plain string should be equivalent to the enum member
    frame = PhysicalFrame(
        user_id=uuid4(),
        commodity="soja",
        side="sell",
        quantity_tons=Decimal("1000.0000"),
        delivery_start=date(2026, 5, 1),
        delivery_end=date(2026, 7, 31),
        status="open",
    )
    assert frame.commodity == "soja"
    assert frame.side == "sell"
    assert frame.quantity_tons == Decimal("1000.0000")


def test_cbot_derivative_option_fields_optional() -> None:
    d = CBOTDerivative(
        user_id=uuid4(),
        commodity=Commodity.MILHO,
        instrument=CBOTInstrument.FUTURE,
        side=Side.BUY,
        contract="ZCN26",
        quantity_contracts=Decimal("10"),
        trade_date=date(2026, 4, 15),
        trade_price=Decimal("615.25"),
        maturity_date=date(2026, 7, 14),
    )
    assert d.option_type is None
    assert d.strike is None
    assert d.barrier_type is None


def test_basis_forward_minimal() -> None:
    b = BasisForward(
        user_id=uuid4(),
        commodity=Commodity.SOJA,
        side=Side.SELL,
        quantity_tons=Decimal("500.0"),
        trade_date=date(2026, 4, 15),
        basis_price=Decimal("-0.45"),
        delivery_date=date(2026, 8, 1),
        reference_cbot_contract="ZSK26",
    )
    assert b.basis_price == Decimal("-0.45")


def test_fx_derivative_ndf_minimal() -> None:
    f = FXDerivative(
        user_id=uuid4(),
        instrument=FXInstrument.NDF,
        side=Side.BUY,
        notional_usd=Decimal("500000.00"),
        trade_date=date(2026, 4, 15),
        trade_rate=Decimal("5.0234"),
        maturity_date=date(2026, 7, 15),
    )
    assert f.instrument == FXInstrument.NDF
    assert f.notional_usd == Decimal("500000.00")


def test_trade_event_payload_jsonb() -> None:
    ev = TradeEvent(
        user_id=uuid4(),
        event_type="fill",
        instrument_table="cbot_derivatives",
        instrument_id=uuid4(),
        quantity=Decimal("5"),
        price=Decimal("1430.00"),
        payload={"note": "partial fill", "nested": [1, 2, 3]},
    )
    assert ev.payload is not None
    assert ev.payload["nested"] == [1, 2, 3]


# ---------------------------------------------------------------------------
# Pydantic schema validators — FixationMode x legs CHECK constraint
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mode", "cbot_fixed", "basis_fixed", "fx_fixed"),
    [
        (FixationMode.FLAT, Decimal("1420"), Decimal("0.50"), Decimal("5.00")),
        (FixationMode.CBOT, Decimal("1420"), None, None),
        (FixationMode.CBOT_BASIS, Decimal("1420"), Decimal("0.50"), None),
        (FixationMode.BASIS, None, Decimal("0.50"), None),
        (FixationMode.FX, None, None, Decimal("5.00")),
    ],
)
def test_physical_fixation_valid_modes(
    mode: FixationMode,
    cbot_fixed: Decimal | None,
    basis_fixed: Decimal | None,
    fx_fixed: Decimal | None,
) -> None:
    fx = PhysicalFixationIn(
        fixation_mode=mode.value,  # type: ignore[arg-type]
        quantity_tons=Decimal("250"),
        fixation_date=date(2026, 4, 15),
        cbot_fixed=cbot_fixed,
        basis_fixed=basis_fixed,
        fx_fixed=fx_fixed,
    )
    assert fx.fixation_mode == mode.value


@pytest.mark.parametrize(
    ("mode", "cbot_fixed", "basis_fixed", "fx_fixed"),
    [
        # Flat: missing one of the 3 legs
        (FixationMode.FLAT, Decimal("1420"), Decimal("0.50"), None),
        (FixationMode.FLAT, None, Decimal("0.50"), Decimal("5")),
        # CBOT: extra leg set
        (FixationMode.CBOT, Decimal("1420"), Decimal("0.50"), None),
        (FixationMode.CBOT, Decimal("1420"), None, Decimal("5")),
        # CBOT_BASIS: fx leg leaked
        (FixationMode.CBOT_BASIS, Decimal("1420"), Decimal("0.50"), Decimal("5")),
        # CBOT_BASIS: missing basis
        (FixationMode.CBOT_BASIS, Decimal("1420"), None, None),
        # BASIS: cbot extra
        (FixationMode.BASIS, Decimal("1420"), Decimal("0.50"), None),
        # BASIS: missing basis_fixed
        (FixationMode.BASIS, None, None, None),
        # FX: cbot extra
        (FixationMode.FX, Decimal("1420"), None, Decimal("5")),
        # FX: missing fx_fixed
        (FixationMode.FX, None, None, None),
    ],
)
def test_physical_fixation_invalid_modes(
    mode: FixationMode,
    cbot_fixed: Decimal | None,
    basis_fixed: Decimal | None,
    fx_fixed: Decimal | None,
) -> None:
    with pytest.raises(ValidationError):
        PhysicalFixationIn(
            fixation_mode=mode.value,  # type: ignore[arg-type]
            quantity_tons=Decimal("250"),
            fixation_date=date(2026, 4, 15),
            cbot_fixed=cbot_fixed,
            basis_fixed=basis_fixed,
            fx_fixed=fx_fixed,
        )


# ---------------------------------------------------------------------------
# Pydantic In schemas — smoke tests for the rest of the families
# ---------------------------------------------------------------------------


def test_physical_frame_in_enum_literal() -> None:
    frame = PhysicalFrameIn(
        commodity="soja",
        side="sell",
        quantity_tons=Decimal("1000"),
        delivery_start=date(2026, 5, 1),
        delivery_end=date(2026, 7, 31),
    )
    assert frame.commodity == "soja"


def test_cbot_derivative_in_minimal() -> None:
    d = CBOTDerivativeIn(
        commodity="soja",
        instrument="future",
        side="buy",
        contract="ZSK26",
        quantity_contracts=Decimal("5"),
        trade_date=date(2026, 4, 15),
        trade_price=Decimal("1420.00"),
        maturity_date=date(2026, 5, 15),
    )
    assert d.option_type is None


def test_basis_forward_in_minimal() -> None:
    b = BasisForwardIn(
        commodity="milho",
        side="buy",
        quantity_tons=Decimal("100"),
        trade_date=date(2026, 4, 15),
        basis_price=Decimal("-0.30"),
        delivery_date=date(2026, 7, 15),
        reference_cbot_contract="ZCN26",
    )
    assert b.reference_cbot_contract == "ZCN26"


def test_fx_derivative_in_option_fields() -> None:
    f = FXDerivativeIn(
        instrument="european_option",
        side="buy",
        notional_usd=Decimal("1000000"),
        trade_date=date(2026, 4, 15),
        trade_rate=Decimal("5.00"),
        maturity_date=date(2026, 7, 15),
        option_type="call",
        strike=Decimal("5.20"),
    )
    assert f.option_type == "call"
    assert f.strike == Decimal("5.20")


def test_price_in_literal_source() -> None:
    p = PriceIn(
        observed_at=datetime(2026, 4, 15, tzinfo=UTC),
        instrument="ZS=F",
        commodity="soja",
        value=Decimal("1420.75"),
        unit="USc/bu",
        price_source="YFINANCE_CBOT",
    )
    assert p.price_source == "YFINANCE_CBOT"


def test_price_in_rejects_unknown_source() -> None:
    with pytest.raises(ValidationError):
        PriceIn(
            observed_at=datetime(2026, 4, 15, tzinfo=UTC),
            instrument="ZS=F",
            value=Decimal("1420"),
            unit="USc/bu",
            price_source="MADE_UP_SOURCE",  # type: ignore[arg-type]
        )
