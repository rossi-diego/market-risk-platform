"""Airflow DAG: daily commodity + FX price pipeline.

Runs 18:00 BRT weekdays. Fetches CBOT soy, CBOT corn (proxy for B3 milho),
and USDBRL FX from yfinance, validates the batch, upserts to the Supabase
`prices` table, and triggers an MTM recalculation on the backend.

In the demo deployment the same logic runs via `.github/workflows/price_update.yml`;
this DAG is the "production-shape" equivalent kept as a portfolio artifact.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta
from typing import Any

import structlog

from airflow.decorators import dag, task

logger = structlog.get_logger(__name__)


DEFAULT_ARGS = {
    "owner": "diego",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="commodity_price_pipeline",
    description="Fetch ZS=F, ZC=F, USDBRL=X from yfinance and upsert to Supabase prices.",
    schedule="0 18 * * 1-5",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["commodity", "market-risk"],
)
def commodity_price_pipeline() -> None:
    """Pipeline: three parallel fetches → validate → upsert → trigger MTM recalc."""

    @task()
    def fetch_soy() -> dict[str, Any]:
        """Fetch ZS=F (soja CBOT front-month) and return a serializable PriceRecord dict."""
        from app.services.price_ingestion import fetch_cbot_soja

        r = fetch_cbot_soja()
        return {
            "observed_at": r.observed_at.isoformat(),
            "instrument": r.instrument,
            "commodity": r.commodity.value if r.commodity else None,
            "value": str(r.value),
            "unit": r.unit,
            "price_source": r.price_source.value,
        }

    @task()
    def fetch_corn() -> dict[str, Any]:
        """Fetch ZC=F (milho proxy) and return a serializable PriceRecord dict."""
        from app.services.price_ingestion import fetch_cbot_milho

        r = fetch_cbot_milho()
        return {
            "observed_at": r.observed_at.isoformat(),
            "instrument": r.instrument,
            "commodity": r.commodity.value if r.commodity else None,
            "value": str(r.value),
            "unit": r.unit,
            "price_source": r.price_source.value,
        }

    @task()
    def fetch_fx() -> dict[str, Any]:
        """Fetch USDBRL=X and return a serializable PriceRecord dict."""
        from app.services.price_ingestion import fetch_fx_usdbrl

        r = fetch_fx_usdbrl()
        return {
            "observed_at": r.observed_at.isoformat(),
            "instrument": r.instrument,
            "commodity": r.commodity.value if r.commodity else None,
            "value": str(r.value),
            "unit": r.unit,
            "price_source": r.price_source.value,
        }

    @task()
    def validate(soy: dict[str, Any], corn: dict[str, Any], fx: dict[str, Any]) -> list[dict[str, Any]]:
        """Re-hydrate the 3 records, call the shared validator, return dicts again."""
        from decimal import Decimal

        from app.models.enums import Commodity, PriceSource
        from app.services.price_ingestion import PriceRecord, validate_records

        def _rehydrate(d: dict[str, Any]) -> PriceRecord:
            return PriceRecord(
                observed_at=datetime.fromisoformat(d["observed_at"]),
                instrument=d["instrument"],
                commodity=Commodity(d["commodity"]) if d["commodity"] else None,
                value=Decimal(d["value"]),
                unit=d["unit"],
                price_source=PriceSource(d["price_source"]),
            )

        records = [_rehydrate(d) for d in (soy, corn, fx)]
        validate_records(records)
        return [soy, corn, fx]

    @task()
    def upsert_supabase(payload: list[dict[str, Any]]) -> int:
        """Open an async session and upsert the validated records."""
        from decimal import Decimal

        from app.core.db import AsyncSessionLocal, engine
        from app.models.enums import Commodity, PriceSource
        from app.services.price_ingestion import PriceRecord, upsert_prices

        async def _run() -> int:
            records = [
                PriceRecord(
                    observed_at=datetime.fromisoformat(d["observed_at"]),
                    instrument=d["instrument"],
                    commodity=Commodity(d["commodity"]) if d["commodity"] else None,
                    value=Decimal(d["value"]),
                    unit=d["unit"],
                    price_source=PriceSource(d["price_source"]),
                )
                for d in payload
            ]
            try:
                async with AsyncSessionLocal() as session:
                    return await upsert_prices(session, records)
            finally:
                await engine.dispose()

        return asyncio.run(_run())

    @task()
    def trigger_mtm_recalc(upserted: int) -> dict[str, Any]:
        """Placeholder: log-only until Phase 6 adds the /risk/recalculate endpoint."""
        api_url = os.environ.get("API_URL", "http://localhost:8000/api/v1")
        logger.info(
            "mtm_recalc_stub",
            api_url=api_url,
            endpoint="/risk/recalculate",
            upserted=upserted,
            note="Phase 6 wires the real HTTP call.",
        )
        return {"status": "stub", "upserted": upserted}

    soy = fetch_soy()
    corn = fetch_corn()
    fx = fetch_fx()
    validated = validate(soy, corn, fx)
    upserted = upsert_supabase(validated)
    trigger_mtm_recalc(upserted)


dag = commodity_price_pipeline()
