#!/usr/bin/env python
"""CLI entrypoint for the daily price fetch.

Invoked by:
  - `.github/workflows/price_update.yml` (21:00 UTC weekdays, primary)
  - `infra/airflow/dags/commodity_price_pipeline.py` (portfolio artifact)
  - manual: `uv run python scripts/fetch_prices.py [--dry-run] [--date YYYY-MM-DD] [--verbose]`

Exit 0 on success, non-zero on any exception (logged as structured event).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from typing import NoReturn

import structlog

from app.core.db import AsyncSessionLocal, engine
from app.core.logging import configure_logging
from app.services.price_ingestion import (
    PriceRecord,
    fetch_all,
    upsert_prices,
    validate_records,
)

logger = structlog.get_logger(__name__)


def _print_table(records: list[PriceRecord]) -> None:
    header = f"{'INSTRUMENT':<12} {'VALUE':>14} {'UNIT':<10} {'OBSERVED_AT':<30} SOURCE"
    print(header)
    print("-" * len(header))
    for r in records:
        print(
            f"{r.instrument:<12} "
            f"{r.value!s:>14} "
            f"{r.unit:<10} "
            f"{r.observed_at.isoformat():<30} "
            f"{r.price_source.value}"
        )


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch CBOT + FX prices from yfinance")
    p.add_argument("--dry-run", action="store_true", help="Print records without writing to DB")
    p.add_argument("--date", help="YYYY-MM-DD override for the observation day (advisory only)")
    p.add_argument("--verbose", action="store_true", help="Enable DEBUG logging")
    return p.parse_args()


async def main() -> int:
    args = _parse_args()
    configure_logging("DEBUG" if args.verbose else "INFO")

    t0 = time.perf_counter()
    try:
        logger.info("price_update_start", date=args.date, dry_run=args.dry_run)
        records = fetch_all()
        records = validate_records(records)

        if args.dry_run:
            _print_table(records)
            logger.info(
                "price_update_dry_run",
                fetched=len(records),
                duration_ms=int((time.perf_counter() - t0) * 1000),
            )
            return 0

        async with AsyncSessionLocal() as session:
            upserted = await upsert_prices(session, records)

        logger.info(
            "price_update_complete",
            upserted=upserted,
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
        return 0
    except Exception as exc:
        logger.error(
            "price_update_failed",
            error=str(exc),
            error_type=type(exc).__name__,
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
        return 1
    finally:
        await engine.dispose()


def _entrypoint() -> NoReturn:
    sys.exit(asyncio.run(main()))


if __name__ == "__main__":
    _entrypoint()
