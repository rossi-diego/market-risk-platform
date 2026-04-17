# Import Schema — Position Upload (Excel / CSV)

## Purpose

Defines the expected column schema for Excel (.xlsx) and CSV uploads.
Claude should use this schema whenever generating import templates, writing
ingestion code, or validating uploaded files.

---

## Required Columns

| Column name          | Type    | Format / Values                        | Example          |
|----------------------|---------|----------------------------------------|------------------|
| `commodity`          | string  | `soja` or `milho` (lowercase)          | `soja`           |
| `quantity_tons`      | float   | Positive number, metric tons           | `500.0`          |
| `trade_price_brl_ton`| float   | BRL per metric ton at trade date       | `187.50`         |
| `trade_date`         | date    | ISO 8601: `YYYY-MM-DD`                 | `2024-03-15`     |
| `cbot_at_trade`      | float   | USc/bushel at trade date               | `1348.50`        |
| `fx_at_trade`        | float   | BRL/USD at trade date                  | `4.985`          |
| `premium_at_trade`   | float   | USD/bushel, can be negative (discount) | `0.75`           |
| `contract_type`      | string  | `spot` or `forward`                    | `forward`        |

## Optional Columns

| Column name     | Type   | Default     | Notes                              |
|-----------------|--------|-------------|------------------------------------|
| `counterparty`  | string | `null`      | Free text, e.g. trading company    |
| `notes`         | string | `null`      | Free text observations             |
| `price_source`  | string | `USER_MANUAL` | Override if known; see enum below |

## PriceSource Values (for `price_source` column)

- `YFINANCE_CBOT` — sourced from yfinance ZS=F or ZC=F
- `CBOT_PROXY_YFINANCE` — ZC=F used as B3 proxy for milho
- `USER_MANUAL` — typed or imported by user (default)
- `B3_OFFICIAL` — sourced from B3 directly (reserved for future use)

---

## Validation Rules

```python
# backend/app/schemas/imports.py

from pydantic import BaseModel, Field, field_validator
from datetime import date
from decimal import Decimal
from typing import Literal


class PositionImportRow(BaseModel):
    commodity: Literal["soja", "milho"]
    quantity_tons: Decimal = Field(gt=0, le=1_000_000)
    trade_price_brl_ton: Decimal = Field(gt=0)
    trade_date: date
    cbot_at_trade: Decimal = Field(gt=0, description="USc/bu")
    fx_at_trade: Decimal = Field(gt=0, description="BRL/USD")
    premium_at_trade: Decimal = Field(ge=-10.0, le=10.0, description="USD/bu")
    contract_type: Literal["spot", "forward"]
    counterparty: str | None = None
    notes: str | None = None

    @field_validator("trade_date")
    @classmethod
    def date_not_in_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Trade date cannot be in the future")
        return v

    @field_validator("cbot_at_trade")
    @classmethod
    def cbot_sanity_check(cls, v: Decimal) -> Decimal:
        # CBOT soja has historically been between 500 and 2500 USc/bu
        # CBOT milho between 200 and 1000 USc/bu
        # Using wide bounds to catch obvious data entry errors
        if v < 100 or v > 3000:
            raise ValueError(f"CBOT price {v} USc/bu looks unrealistic (expected 100–3000)")
        return v

    @field_validator("fx_at_trade")
    @classmethod
    def fx_sanity_check(cls, v: Decimal) -> Decimal:
        if v < 1.0 or v > 20.0:
            raise ValueError(f"FX rate {v} BRL/USD looks unrealistic (expected 1.0–20.0)")
        return v
```

---

## Excel Template Structure

The downloadable Excel template (`/api/v1/imports/template`) must have:

1. **Sheet 1: "Posições"** — data entry, headers in row 1, data from row 2
2. **Sheet 2: "Instruções"** — column descriptions, valid values, example rows
3. **Sheet 3: "Exemplos"** — 3 pre-filled example rows (1 soja spot, 1 soja forward, 1 milho)

Header row labels (user-friendly, in Portuguese):
```
Produto | Qtd (tons) | Preço Trade (BRL/ton) | Data do Trade | CBOT Trade (USc/bu) | Câmbio Trade (BRL/USD) | Prêmio Trade (USD/bu) | Tipo Contrato | Contraparte | Observações
```

The ingestion code maps these Portuguese labels to the internal English schema.

## Column Name Aliases (for flexible ingestion)

```python
COLUMN_ALIASES = {
    # Portuguese labels from template
    "produto": "commodity",
    "qtd (tons)": "quantity_tons",
    "preço trade (brl/ton)": "trade_price_brl_ton",
    "data do trade": "trade_date",
    "cbot trade (usc/bu)": "cbot_at_trade",
    "câmbio trade (brl/usd)": "fx_at_trade",
    "prêmio trade (usd/bu)": "premium_at_trade",
    "tipo contrato": "contract_type",
    "contraparte": "counterparty",
    "observações": "notes",
    # English aliases (also accepted)
    "product": "commodity",
    "quantity": "quantity_tons",
    "tons": "quantity_tons",
}
```

---

## Error Response Format

Row-level errors must be returned in the import response:

```json
{
  "imported": 8,
  "skipped": 2,
  "errors": [
    {
      "row": 4,
      "column": "cbot_at_trade",
      "value": "abc",
      "error": "Invalid number format"
    },
    {
      "row": 7,
      "column": "trade_date",
      "value": "2026-12-01",
      "error": "Trade date cannot be in the future"
    }
  ],
  "storage_path": "user-uuid/upload-2024-03-15.xlsx"
}
```
