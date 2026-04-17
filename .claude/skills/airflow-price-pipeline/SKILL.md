---
name: airflow-price-pipeline
description: >
  Airflow DAG patterns for the commodity_price_pipeline in the
  commodity-risk-dashboard project. Use this skill whenever working on the
  Airflow DAG that fetches commodity prices (soja CBOT, milho CBOT proxy, FX),
  validates them, upserts to Supabase, and triggers MTM recalculation.
  Also trigger when the user asks about: local Airflow setup with Docker Compose,
  how to test DAGs, connection configuration for Supabase, scheduling the
  price update, or the difference between the Airflow DAG and the GitHub Actions
  cron job that serves the same purpose in the demo deployment.
---

# Airflow Price Pipeline

The `commodity_price_pipeline` DAG is the production-grade price update mechanism.
In the demo deployment it exists as code but is not actively scheduled —
GitHub Actions Cron runs instead (zero infra). In a real deployment,
this DAG would run on Astronomer or self-hosted Airflow.

---

## Two-Track Architecture

```
Demo deploy (portfolio):          Production pattern:
GitHub Actions Cron               Airflow on Astronomer / self-hosted
       ↓                                      ↓
scripts/fetch_prices.py           infra/airflow/dags/commodity_price_pipeline.py
       ↓                                      ↓
POST /api/v1/prices/fetch         direct Supabase upsert + HTTP trigger
```

Both paths ultimately write to the same `prices` table in Supabase.
The Airflow DAG has better retry logic, observability, and task-level granularity.

---

## DAG Definition

```python
# infra/airflow/dags/commodity_price_pipeline.py

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.http import SimpleHttpOperator
from airflow.utils.dates import days_ago

default_args = {
    "owner": "data-engineering",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "email_on_failure": False,  # configure alerting separately
}

with DAG(
    dag_id="commodity_price_pipeline",
    default_args=default_args,
    description="Daily commodity price fetch and MTM trigger",
    schedule="0 21 * * 1-5",  # 18:00 BRT = 21:00 UTC, weekdays
    start_date=days_ago(1),
    catchup=False,
    tags=["commodity", "prices", "risk"],
) as dag:

    fetch_soja = PythonOperator(
        task_id="fetch_soja_cbot",
        python_callable=fetch_and_store_price,
        op_kwargs={"ticker": "ZS=F", "feed": "soja_cbot", "source": "YFINANCE_CBOT"},
    )

    fetch_milho = PythonOperator(
        task_id="fetch_milho_cbot_proxy",
        python_callable=fetch_and_store_price,
        op_kwargs={"ticker": "ZC=F", "feed": "milho_cbot", "source": "CBOT_PROXY_YFINANCE"},
    )

    fetch_fx = PythonOperator(
        task_id="fetch_fx_usdbrl",
        python_callable=fetch_and_store_price,
        op_kwargs={"ticker": "USDBRL=X", "feed": "fx_usdbrl", "source": "YFINANCE_FX"},
    )

    validate = PythonOperator(
        task_id="validate_prices",
        python_callable=validate_today_prices,
    )

    trigger_mtm = SimpleHttpOperator(
        task_id="trigger_mtm_recalculation",
        http_conn_id="commodity_api",  # configured in Airflow Connections UI
        endpoint="/api/v1/risk/recalculate",
        method="POST",
        headers={"Authorization": "Bearer {{ var.value.API_SERVICE_TOKEN }}"},
        response_check=lambda response: response.status_code == 200,
    )

    # Fetch tasks run in parallel, then validate, then trigger MTM
    [fetch_soja, fetch_milho, fetch_fx] >> validate >> trigger_mtm
```

---

## Task Implementations

```python
# infra/airflow/dags/tasks/price_tasks.py

import yfinance as yf
from datetime import date, timedelta
from supabase import create_client
import os
import logging

logger = logging.getLogger(__name__)


def fetch_and_store_price(ticker: str, feed: str, source: str, **context) -> dict:
    """
    Fetch latest price from yfinance and upsert to Supabase.
    Returns fetched record for downstream task communication via XCom.
    """
    client = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )

    # Use 5-day lookback to handle weekends + holidays
    df = yf.download(ticker, period="5d", progress=False)
    if df.empty:
        raise ValueError(f"No data returned for ticker {ticker}")

    latest_close = float(df["Close"].dropna().iloc[-1])
    latest_date = df["Close"].dropna().index[-1].date()

    record = {
        "ticker": ticker,
        "feed_name": feed,
        "price_date": str(latest_date),
        "close_price": latest_close,
        "price_source": source,
    }

    client.table("prices").upsert(
        record,
        on_conflict="ticker,price_date"
    ).execute()

    logger.info(f"Upserted price: {feed} = {latest_close} on {latest_date}")
    return record


def validate_today_prices(**context) -> None:
    """
    Verify that all three feeds have a price for today (or most recent trading day).
    Raises if any feed is missing — blocks MTM trigger.
    """
    client = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )

    required_feeds = ["soja_cbot", "milho_cbot", "fx_usdbrl"]
    cutoff = date.today() - timedelta(days=5)

    result = (
        client.table("prices")
        .select("feed_name, price_date")
        .gte("price_date", str(cutoff))
        .execute()
    )

    fetched_feeds = {row["feed_name"] for row in result.data}
    missing = set(required_feeds) - fetched_feeds

    if missing:
        raise ValueError(f"Price validation failed. Missing feeds: {missing}")

    logger.info("Price validation passed for all feeds.")
```

---

## Local Development Setup

```yaml
# infra/docker-compose.yml (Airflow section)

version: "3.8"
services:
  airflow-webserver:
    image: apache/airflow:2.9.0
    environment:
      AIRFLOW__CORE__EXECUTOR: LocalExecutor
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@airflow-db/airflow
      AIRFLOW__CORE__LOAD_EXAMPLES: "false"
      SUPABASE_URL: ${SUPABASE_URL}
      SUPABASE_SERVICE_ROLE_KEY: ${SUPABASE_SERVICE_ROLE_KEY}
    volumes:
      - ./airflow/dags:/opt/airflow/dags
      - ./airflow/logs:/opt/airflow/logs
    ports:
      - "8080:8080"
    command: webserver
    depends_on:
      - airflow-db

  airflow-scheduler:
    image: apache/airflow:2.9.0
    environment:
      AIRFLOW__CORE__EXECUTOR: LocalExecutor
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@airflow-db/airflow
      SUPABASE_URL: ${SUPABASE_URL}
      SUPABASE_SERVICE_ROLE_KEY: ${SUPABASE_SERVICE_ROLE_KEY}
    volumes:
      - ./airflow/dags:/opt/airflow/dags
    command: scheduler
    depends_on:
      - airflow-db

  airflow-db:
    image: postgres:15
    environment:
      POSTGRES_USER: airflow
      POSTGRES_PASSWORD: airflow
      POSTGRES_DB: airflow
    volumes:
      - airflow_db_data:/var/lib/postgresql/data

volumes:
  airflow_db_data:
```

Initialize Airflow DB on first run:
```bash
docker compose run --rm airflow-webserver airflow db init
docker compose run --rm airflow-webserver airflow users create \
  --username admin --password admin --firstname Admin \
  --lastname User --role Admin --email admin@localhost
```

---

## Connections & Variables

Configure in Airflow UI (Admin → Connections):

| Conn ID          | Type  | Host                        | Extra                          |
|------------------|-------|-----------------------------|--------------------------------|
| `commodity_api`  | HTTP  | `https://your-api.render.com` | `{"Authorization": "Bearer ..."}` |

Configure in Airflow Variables (Admin → Variables):

| Key                  | Value              |
|----------------------|--------------------|
| `API_SERVICE_TOKEN`  | Backend service JWT|

---

## GitHub Actions Cron (Demo Equivalent)

```yaml
# .github/workflows/price_update.yml
name: Daily Price Update

on:
  schedule:
    - cron: '0 21 * * 1-5'   # 18:00 BRT = 21:00 UTC
  workflow_dispatch:           # allow manual trigger

jobs:
  fetch-prices:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3

      - name: Fetch prices
        run: uv run python scripts/fetch_prices.py
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}

      - name: Trigger MTM recalculation
        run: |
          curl -X POST ${{ secrets.API_URL }}/api/v1/risk/recalculate \
            -H "Authorization: Bearer ${{ secrets.API_SERVICE_TOKEN }}" \
            -f  # fail on HTTP errors
```
