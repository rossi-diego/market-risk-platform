# Stress Test Scenarios Reference

## Historical Scenarios (hard-coded)

```python
# backend/app/risk/stress.py

HISTORICAL_SCENARIOS = [
    {
        "name": "2008 Global Financial Crisis",
        "type": "historical",
        "period": "Sep–Dec 2008",
        "soja_shock_pct": -35.0,
        "milho_shock_pct": -42.0,
        "fx_shock_pct": +40.0,   # BRL weakened sharply vs USD
        "description": (
            "Lehman collapse triggered commodity selloff and EM currency crisis. "
            "Soy fell from $15.94/bu (Jul 2008) to $8.19/bu (Dec 2008). "
            "BRL/USD moved from ~1.58 to ~2.40."
        ),
        "source": "CBOT historical data; BCB exchange rates",
    },
    {
        "name": "2012 US Midwest Drought",
        "type": "historical",
        "period": "Jun–Aug 2012",
        "soja_shock_pct": +35.0,
        "milho_shock_pct": +45.0,
        "fx_shock_pct": +8.0,
        "description": (
            "Worst US drought since 1956 devastated corn and soy crops. "
            "Corn hit record $8.49/bu (Aug 2012). Soy reached $17.89/bu. "
            "For Brazilian producers with long positions, this was a windfall."
        ),
        "source": "USDA drought reports; CBOT archives",
    },
    {
        "name": "2020 COVID-19 Shock",
        "type": "historical",
        "period": "Feb–Mar 2020",
        "soja_shock_pct": -12.0,
        "milho_shock_pct": -18.0,
        "fx_shock_pct": +35.0,   # BRL hit record lows
        "description": (
            "Pandemic panic caused commodity selloff, but BRL collapse partially offset "
            "losses for Brazilian producers. BRL/USD went from 4.03 to 5.70 in weeks. "
            "Net effect on BRL/ton varied by hedge position."
        ),
        "source": "BCB; CBOT; B3 historical",
    },
    {
        "name": "2022 Ukraine War — Supply Shock",
        "type": "historical",
        "period": "Feb–May 2022",
        "soja_shock_pct": +25.0,
        "milho_shock_pct": +30.0,
        "fx_shock_pct": -5.0,    # BRL actually strengthened (commodity exporter)
        "description": (
            "Russia invasion of Ukraine disrupted Black Sea grain corridor. "
            "Ukraine supplies ~15% of world corn and ~9% of wheat. "
            "Brazil benefited as alternative supplier; BRL strengthened. "
            "For unhedged long positions in Brazil, double positive."
        ),
        "source": "USDA; FAO; BCB; CBOT",
    },
]
```

## Hypothetical Scenario Schema

```python
# Schema for user-configured hypothetical scenarios

HYPOTHETICAL_SCENARIO_SCHEMA = {
    "name": str,                    # user label
    "type": "hypothetical",
    "soja_shock_pct": float,        # range: -80% to +200%
    "milho_shock_pct": float,
    "fx_shock_pct": float,
    "description": str | None,
}
```

## Validation Rules

- Shocks are **multiplicative**: `shocked = current × (1 + shock/100)`
- Minimum reasonable shock: ±2% (below this, likely user input error)
- Maximum allowed shock: ±90% (prevents nonsensical negative prices)
- FX shock interpretation: positive = BRL weakens (e.g. +10% means BRL/USD goes up 10%)
- For soja/milho long positions: negative price shock = loss, positive FX shock = gain
  (the FX effect partially offsets commodity price moves — this is the key insight of decomposition)

## Literature References for Stress Testing

- Jorion, P. (2006). *Value at Risk*, 3rd ed. McGraw-Hill. Chapter 14.
- Basel Committee on Banking Supervision (2009). *Principles for Sound Stress Testing Practices*.
- Basel Committee on Banking Supervision (2016). *Minimum Capital Requirements for Market Risk* (FRTB).
- CME Group. *SPAN Margin Methodology* (Standard Portfolio Analysis of Risk).
- CONAB. *Acompanhamento da Safra Brasileira* (quarterly crop surveys for context).
