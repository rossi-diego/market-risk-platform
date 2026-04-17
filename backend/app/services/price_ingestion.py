"""Price ingestion: yfinance fetch → validate → upsert to `prices`.

Tickers (CLAUDE.md > Data Sources):
  - ZS=F      → soja CBOT front-month, USc/bu, price_source=YFINANCE_CBOT
  - ZC=F      → milho proxy, USc/bu, price_source=CBOT_PROXY_YFINANCE
  - USDBRL=X  → FX, BRL/USD, price_source=YFINANCE_FX

`validate_records` enforces positive values and a staleness floor (default
5 business days). `upsert_prices` writes with INSERT … ON CONFLICT on
(observed_at, instrument) so daily re-runs are idempotent.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import structlog
import yfinance as yf
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Commodity, PriceSource

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class PriceRecord:
    observed_at: datetime
    instrument: str
    commodity: Commodity | None
    value: Decimal
    unit: str
    price_source: PriceSource


def _last_close(ticker: str) -> tuple[datetime, Decimal]:
    """Return the (timestamp, close) of the most recent bar over the last 5 days."""
    hist = yf.Ticker(ticker).history(period="5d")
    if hist.empty:
        raise RuntimeError(f"yfinance returned no history for {ticker!r}")
    last = hist.iloc[-1]
    ts_index = hist.index[-1]
    ts = ts_index.to_pydatetime() if hasattr(ts_index, "to_pydatetime") else ts_index
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    close_val = Decimal(str(last["Close"]))
    return ts, close_val


def fetch_cbot_soja() -> PriceRecord:
    ts, value = _last_close("ZS=F")
    return PriceRecord(
        observed_at=ts,
        instrument="ZS=F",
        commodity=Commodity.SOJA,
        value=value,
        unit="USc/bu",
        price_source=PriceSource.YFINANCE_CBOT,
    )


def fetch_cbot_milho() -> PriceRecord:
    ts, value = _last_close("ZC=F")
    return PriceRecord(
        observed_at=ts,
        instrument="ZC=F",
        commodity=Commodity.MILHO,
        value=value,
        unit="USc/bu",
        price_source=PriceSource.CBOT_PROXY_YFINANCE,
    )


def fetch_fx_usdbrl() -> PriceRecord:
    ts, value = _last_close("USDBRL=X")
    return PriceRecord(
        observed_at=ts,
        instrument="USDBRL=X",
        commodity=None,
        value=value,
        unit="BRL/USD",
        price_source=PriceSource.YFINANCE_FX,
    )


def fetch_all() -> list[PriceRecord]:
    return [fetch_cbot_soja(), fetch_cbot_milho(), fetch_fx_usdbrl()]


def _business_days_ago(days: int) -> datetime:
    """Conservative business-day staleness: subtract `days * 7 / 5` calendar days.

    A full weekend lookback buffer keeps Monday runs from failing on
    Friday's stamp.
    """
    calendar_days = int(days * 7 / 5) + 2
    return datetime.now(tz=UTC) - timedelta(days=calendar_days)


def validate_records(records: list[PriceRecord], max_staleness_days: int = 5) -> list[PriceRecord]:
    """Reject non-positive values or stamps older than `max_staleness_days`.

    Raises `ValueError` on first violation. Logs each violation with
    structured fields for observability.
    """
    cutoff = _business_days_ago(max_staleness_days)
    for r in records:
        observed_at = (
            r.observed_at if r.observed_at.tzinfo is not None else r.observed_at.replace(tzinfo=UTC)
        )
        ctx = {
            "instrument": r.instrument,
            "value": str(r.value),
            "observed_at": observed_at.isoformat(),
            "price_source": r.price_source.value,
        }
        if r.value <= 0:
            logger.error("price_invalid_value", **ctx)
            raise ValueError(f"Invalid price value for {r.instrument}: {r.value}")
        if observed_at < cutoff:
            logger.error("price_stale", cutoff=cutoff.isoformat(), **ctx)
            raise ValueError(
                f"Stale price for {r.instrument}: {observed_at.isoformat()} < {cutoff.isoformat()}"
            )
    return records


_UPSERT_SQL = text("""
    INSERT INTO prices (observed_at, instrument, commodity, value, unit, price_source)
    VALUES (:observed_at, :instrument, :commodity, :value, :unit, :price_source)
    ON CONFLICT (observed_at, instrument)
    DO UPDATE SET
        value = EXCLUDED.value,
        price_source = EXCLUDED.price_source,
        commodity = EXCLUDED.commodity,
        unit = EXCLUDED.unit
""")


async def upsert_prices(session: AsyncSession, records: list[PriceRecord]) -> int:
    """Upsert each record; returns the total number of rows written."""
    if not records:
        return 0
    params: list[dict[str, Any]] = [
        {
            "observed_at": r.observed_at,
            "instrument": r.instrument,
            "commodity": r.commodity.value if r.commodity is not None else None,
            "value": r.value,
            "unit": r.unit,
            "price_source": r.price_source.value,
        }
        for r in records
    ]
    result = await session.execute(_UPSERT_SQL, params)
    await session.commit()
    # SQLAlchemy with executemany returns -1 for rowcount on asyncpg; fall back to len.
    rowcount: int = getattr(result, "rowcount", 0) or 0
    return rowcount if rowcount > 0 else len(records)
