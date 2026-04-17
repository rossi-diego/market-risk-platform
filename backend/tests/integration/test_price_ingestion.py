"""Tests for app.services.price_ingestion.

Unit tests (yfinance-mocked, pure): always run.
Integration tests (hit real Supabase): gated behind `--run-integration`.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pandas as pd
import pytest
from pytest_mock import MockerFixture

from app.models.enums import Commodity, PriceSource
from app.services.price_ingestion import (
    PriceRecord,
    fetch_cbot_milho,
    fetch_cbot_soja,
    fetch_fx_usdbrl,
    validate_records,
)

# ---------------------------------------------------------------------------
# yfinance.Ticker stub
# ---------------------------------------------------------------------------


def _stub_history(ticker_symbol: str, close: float = 1420.5) -> pd.DataFrame:
    """Return a DataFrame shaped like yfinance's Ticker.history() output."""
    ts = pd.Timestamp.now(tz="UTC").floor("D")
    return pd.DataFrame(
        {
            "Open": [close - 1],
            "High": [close + 2],
            "Low": [close - 3],
            "Close": [close],
            "Volume": [1_000_000],
        },
        index=pd.DatetimeIndex([ts], name="Date"),
    )


class _StubTicker:
    def __init__(self, ticker: str, close: float = 1420.5) -> None:
        self.ticker = ticker
        self._close = close

    def history(self, period: str = "5d", **_: Any) -> pd.DataFrame:
        return _stub_history(self.ticker, close=self._close)


@pytest.fixture
def mock_yf(mocker: MockerFixture) -> None:
    def factory(ticker: str) -> _StubTicker:
        defaults = {"ZS=F": 1420.5, "ZC=F": 625.25, "USDBRL=X": 5.03}
        return _StubTicker(ticker, close=defaults.get(ticker, 100.0))

    mocker.patch("app.services.price_ingestion.yf.Ticker", side_effect=factory)


# ---------------------------------------------------------------------------
# Fetchers — unit tests
# ---------------------------------------------------------------------------


def test_fetch_cbot_soja_returns_record(mock_yf: None) -> None:
    r = fetch_cbot_soja()
    assert r.instrument == "ZS=F"
    assert r.commodity is Commodity.SOJA
    assert r.unit == "USc/bu"
    assert r.price_source is PriceSource.YFINANCE_CBOT
    assert r.value == Decimal("1420.5")


def test_fetch_cbot_milho_uses_proxy_flag(mock_yf: None) -> None:
    r = fetch_cbot_milho()
    assert r.instrument == "ZC=F"
    assert r.commodity is Commodity.MILHO
    assert r.price_source is PriceSource.CBOT_PROXY_YFINANCE
    assert r.unit == "USc/bu"


def test_fetch_fx_usdbrl_no_commodity(mock_yf: None) -> None:
    r = fetch_fx_usdbrl()
    assert r.instrument == "USDBRL=X"
    assert r.commodity is None
    assert r.price_source is PriceSource.YFINANCE_FX
    assert r.unit == "BRL/USD"


def test_fetch_raises_on_empty_history(mocker: MockerFixture) -> None:
    class _Empty:
        def history(self, **_: Any) -> pd.DataFrame:
            return pd.DataFrame()

    mocker.patch("app.services.price_ingestion.yf.Ticker", return_value=_Empty())
    with pytest.raises(RuntimeError, match="no history"):
        fetch_cbot_soja()


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


def _record(value: str = "10", age_days: int = 0) -> PriceRecord:
    return PriceRecord(
        observed_at=datetime.now(tz=UTC) - timedelta(days=age_days),
        instrument="ZS=F",
        commodity=Commodity.SOJA,
        value=Decimal(value),
        unit="USc/bu",
        price_source=PriceSource.YFINANCE_CBOT,
    )


def test_validate_accepts_fresh_positive() -> None:
    out = validate_records([_record(value="1420.5", age_days=0)])
    assert len(out) == 1


@pytest.mark.parametrize("bad_value", ["0", "-1", "-1420.5"])
def test_validate_rejects_zero_or_negative(bad_value: str) -> None:
    with pytest.raises(ValueError, match="Invalid price value"):
        validate_records([_record(value=bad_value)])


def test_validate_rejects_stale() -> None:
    # 15 calendar days is well past any 5-business-day window.
    with pytest.raises(ValueError, match="Stale price"):
        validate_records([_record(age_days=15)])


def test_validate_naive_datetime_is_treated_as_utc() -> None:
    r = PriceRecord(
        observed_at=datetime.now(),  # naive
        instrument="ZS=F",
        commodity=Commodity.SOJA,
        value=Decimal("100"),
        unit="USc/bu",
        price_source=PriceSource.YFINANCE_CBOT,
    )
    out = validate_records([r])
    assert len(out) == 1


# ---------------------------------------------------------------------------
# Integration — real DB upsert (skipped by default)
# ---------------------------------------------------------------------------


pytestmark_integration = pytest.mark.integration


def _integration_ready() -> bool:
    return bool(os.environ.get("SUPABASE_URL", "").startswith("https://")) and not os.environ[
        "SUPABASE_URL"
    ].startswith("https://example.")


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(not _integration_ready(), reason="SUPABASE_URL not configured")
async def test_upsert_idempotent() -> None:
    from sqlalchemy import text

    from app.core.db import AsyncSessionLocal, engine
    from app.services.price_ingestion import upsert_prices

    r = PriceRecord(
        observed_at=datetime(2026, 1, 2, 21, 0, tzinfo=UTC),
        instrument="TEST_ZS=F",
        commodity=Commodity.SOJA,
        value=Decimal("1000"),
        unit="USc/bu",
        price_source=PriceSource.USER_MANUAL,
    )
    try:
        async with AsyncSessionLocal() as session:
            await upsert_prices(session, [r])
            await upsert_prices(session, [r])  # second call must not duplicate
            rows = (
                await session.execute(
                    text("SELECT count(*) FROM prices WHERE instrument = :i AND observed_at = :t"),
                    {"i": "TEST_ZS=F", "t": r.observed_at},
                )
            ).scalar_one()
            assert rows == 1
            await session.execute(
                text("DELETE FROM prices WHERE instrument = 'TEST_ZS=F'"),
            )
            await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(not _integration_ready(), reason="SUPABASE_URL not configured")
async def test_upsert_updates_on_conflict() -> None:
    from sqlalchemy import text

    from app.core.db import AsyncSessionLocal, engine
    from app.services.price_ingestion import upsert_prices

    ts = datetime(2026, 1, 3, 21, 0, tzinfo=UTC)
    r1 = PriceRecord(
        observed_at=ts,
        instrument="TEST_UPD=F",
        commodity=Commodity.SOJA,
        value=Decimal("1000"),
        unit="USc/bu",
        price_source=PriceSource.USER_MANUAL,
    )
    r2 = PriceRecord(
        observed_at=ts,
        instrument="TEST_UPD=F",
        commodity=Commodity.SOJA,
        value=Decimal("1500"),
        unit="USc/bu",
        price_source=PriceSource.USER_MANUAL,
    )
    try:
        async with AsyncSessionLocal() as session:
            await upsert_prices(session, [r1])
            await upsert_prices(session, [r2])
            val = (
                await session.execute(
                    text("SELECT value FROM prices WHERE instrument = 'TEST_UPD=F'"),
                )
            ).scalar_one()
            assert Decimal(str(val)) == Decimal("1500")
            await session.execute(text("DELETE FROM prices WHERE instrument = 'TEST_UPD=F'"))
            await session.commit()
    finally:
        await engine.dispose()
