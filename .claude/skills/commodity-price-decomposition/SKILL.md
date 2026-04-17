---
name: commodity-price-decomposition
description: >
  Core price formation model for soybean (soja) and corn (milho) in the Brazilian
  agribusiness context. Use this skill whenever working on any part of the
  commodity-risk-dashboard that involves: price calculations, unit conversions
  (USc/bu → BRL/ton), MTM decomposition (CBOT delta, FX delta, premium delta),
  price source flags, yfinance ticker mapping, premium configuration, or any
  mention of CBOT, prêmio, FX, dólar, saca, bushel, or ton. Also trigger for
  questions about why corn uses ZC=F as a proxy, how to implement the BRL/ton
  formula, or how to separate exposure components per position.
---

# Commodity Price Decomposition

This skill defines the canonical price formation model for the project.
Every risk calculation, MTM computation, and exposure report derives from these formulas.
Never deviate from or approximate these — unit conversion errors compound.

---

## Price Formation Formulas

### Soybean (Soja)

```
Price [BRL/ton] = (CBOT [USc/bu] / 100 / 36.744) × FX [BRL/USD]
                + (Premium [USD/bu] / 36.744) × FX [BRL/USD]
```

Simplified:
```
Price [BRL/ton] = (CBOT [USc/bu] + Premium_in_USc [USc/bu]) / 100 / 36.744 × FX
```

- CBOT source: yfinance ticker `ZS=F` (front-month CBOT, USc/bushel)
- FX source: yfinance ticker `USDBRL=X` (BRL per 1 USD)
- Conversion: **1 metric ton soja = 36.744 bushels**
- Premium: user-supplied per operation (trade premium) and globally per MTM config

### Corn (Milho)

```
Price [BRL/ton] = (CBOT [USc/bu] / 100 / 56.0) × FX [BRL/USD]
                + (Premium [USD/bu] / 56.0) × FX [BRL/USD]
```

- CBOT source: yfinance ticker `ZC=F` — **PROXY ONLY** (ideally B3 `CCM`, unavailable via free API)
- FX source: same `USDBRL=X`
- Conversion: **1 metric ton milho = 56.0 bushels**
- Every price record using ZC=F must carry `price_source = PriceSource.CBOT_PROXY`

---

## Reference Implementation

```python
# backend/app/risk/pricing.py

from decimal import Decimal
from dataclasses import dataclass
from app.models.enums import PriceSource


SOJA_BUSHELS_PER_TON: float = 36.744
MILHO_BUSHELS_PER_TON: float = 56.0


@dataclass(frozen=True)
class PriceComponents:
    """Decomposed price in BRL/ton for a single commodity position."""
    cbot_component_brl_ton: Decimal   # contribution from CBOT alone
    fx_is_implicit: bool              # FX is multiplicative, not additive
    premium_component_brl_ton: Decimal
    total_brl_ton: Decimal
    price_source: PriceSource


def usc_per_bu_to_brl_ton(
    cbot_usc_per_bu: float,
    fx_brl_per_usd: float,
    premium_usd_per_bu: float,
    commodity: str,  # "soja" | "milho"
    price_source: PriceSource,
) -> PriceComponents:
    """
    Convert CBOT (USc/bu) + premium (USD/bu) + FX (BRL/USD) to BRL/ton.

    Args:
        cbot_usc_per_bu: CBOT price in US cents per bushel (e.g. 1350.0)
        fx_brl_per_usd: FX rate BRL per 1 USD (e.g. 5.05)
        premium_usd_per_bu: basis/premium in USD per bushel (e.g. 0.80)
        commodity: "soja" or "milho"
        price_source: origin of the CBOT price

    Returns:
        PriceComponents with full decomposition
    """
    factor = SOJA_BUSHELS_PER_TON if commodity == "soja" else MILHO_BUSHELS_PER_TON

    cbot_usd_per_ton = (cbot_usc_per_bu / 100) / factor
    premium_usd_per_ton = premium_usd_per_bu / factor

    cbot_brl = Decimal(str(cbot_usd_per_ton * fx_brl_per_usd))
    premium_brl = Decimal(str(premium_usd_per_ton * fx_brl_per_usd))
    total_brl = cbot_brl + premium_brl

    return PriceComponents(
        cbot_component_brl_ton=cbot_brl,
        fx_is_implicit=True,
        premium_component_brl_ton=premium_brl,
        total_brl_ton=total_brl,
        price_source=price_source,
    )
```

---

## MTM P&L Decomposition

Each position's unrealized P&L must be broken into three independent components
so traders can see **what is driving their exposure**:

```python
@dataclass(frozen=True)
class ExposureDecomposition:
    """
    P&L sensitivity per unit move for a position of Q tons.
    All values in BRL.
    """
    quantity_tons: Decimal

    # CBOT delta: BRL P&L change per 1 USc/bu CBOT move
    cbot_delta_brl_per_usc_bu: Decimal

    # FX delta: BRL P&L change per 0.01 BRL/USD FX move
    fx_delta_brl_per_cent_fx: Decimal

    # Premium delta: BRL P&L change per 1 USD/bu premium move
    premium_delta_brl_per_usd_bu: Decimal

    # Actual MTM P&L components at current market
    cbot_pnl_brl: Decimal
    fx_pnl_brl: Decimal
    premium_pnl_brl: Decimal
    total_pnl_brl: Decimal
```

**Calculation logic:**

```
cbot_delta [BRL/(USc/bu)] = Q_tons / factor / 100 × FX_current

fx_delta [BRL/0.01 FX]   = Q_tons × (CBOT_current/100 + Premium_current) / factor × 0.01

premium_delta [BRL/(USD/bu)] = Q_tons / factor × FX_current
```

---

## Price Source Enum

```python
# backend/app/models/enums.py

from enum import Enum

class PriceSource(str, Enum):
    YFINANCE_CBOT    = "YFINANCE_CBOT"        # ZS=F via yfinance
    YFINANCE_FX      = "YFINANCE_FX"          # USDBRL=X via yfinance
    CBOT_PROXY       = "CBOT_PROXY_YFINANCE"  # ZC=F standing in for B3 CCM
    B3_OFFICIAL      = "B3_OFFICIAL"          # future: B3 CCM direct
    USER_MANUAL      = "USER_MANUAL"          # typed or imported by user
```

Every `Price` DB record and every computed MTM result must carry a `price_source` field.
Risk results derived from proxy data must be flagged in API responses with a
`data_quality_warning` field.

---

## yfinance Fetch Pattern

```python
# backend/app/services/price_fetcher.py

import yfinance as yf
import pandas as pd
from datetime import date, timedelta


TICKERS = {
    "soja_cbot":  ("ZS=F",    PriceSource.YFINANCE_CBOT),
    "milho_cbot": ("ZC=F",    PriceSource.CBOT_PROXY),
    "fx_usdbrl":  ("USDBRL=X", PriceSource.YFINANCE_FX),
}


def fetch_latest_prices(lookback_days: int = 5) -> dict:
    """
    Fetch latest available close prices for all feeds.
    Uses lookback_days to handle weekends and market holidays.
    Returns dict keyed by feed name with (price, date, source) tuples.
    """
    end = date.today()
    start = end - timedelta(days=lookback_days)
    results = {}

    for feed_name, (ticker, source) in TICKERS.items():
        df = yf.download(ticker, start=start, end=end, progress=False)
        if df.empty:
            results[feed_name] = None
            continue
        latest = df["Close"].dropna().iloc[-1]
        latest_date = df["Close"].dropna().index[-1].date()
        results[feed_name] = {"price": float(latest), "date": latest_date, "source": source}

    return results
```

---

## MTM Premium Configuration

Two separate premium concepts exist in the system:

| Premium type    | Scope           | Usage                                      |
|-----------------|-----------------|--------------------------------------------|
| `trade_premium` | Per position    | Stored at trade time, never changes        |
| `mtm_premium`   | Global per crop | Used for current MTM calculation, editable |

The `mtm_premium` lives in a `mtm_config` table (one row per commodity).
When recalculating MTM, always use `mtm_premium`, not `trade_premium`.
Both must be exposed in the position detail view for transparency.

---

## Common Errors to Avoid

- **Never** convert BRL/saca (60kg) to BRL/ton by dividing by 60 inline — use the bushel path only
- **Never** use `ZC=F` without setting `price_source = PriceSource.CBOT_PROXY`
- **Never** mix trade premium and MTM premium in the same calculation
- `USDBRL=X` in yfinance is already BRL/USD (not USD/BRL) — confirm before inverting
- CBOT prices from yfinance come in USc/bu (e.g. 1350 = $13.50/bu) — always divide by 100 first
