---
name: risk-engine-patterns
description: >
  Production-grade implementation patterns for market risk metrics in the
  commodity-risk-dashboard project. Use this skill whenever working on VaR
  (Value at Risk), CVaR (Conditional VaR / Expected Shortfall), stress testing,
  Monte Carlo simulation, historical simulation, parametric VaR, risk decomposition,
  P&L attribution, or any calculation in the backend/app/risk/ module.
  Also trigger when the user asks about Basel III/IV, FRTB, Jorion, Hull,
  risk methodology documentation, seed-controlled MC, or how to validate
  risk engine outputs. This skill enforces correct formulas, correct literature
  references, reproducible randomness, and typed outputs.
---

# Risk Engine Patterns

Canonical implementation patterns for VaR, CVaR, and stress testing.
All functions in `backend/app/risk/` must follow these patterns.

See reference files for deeper implementation details:
- `references/var_implementations.md` — full VaR code with tests
- `references/stress_scenarios.md` — historical scenario definitions

---

## Module Structure

```
backend/app/risk/
├── __init__.py
├── pricing.py          # BRL/ton formula (see commodity-price-decomposition skill)
├── returns.py          # price series → return series utilities
├── var.py              # VaR: historical, parametric, Monte Carlo
├── cvar.py             # CVaR / Expected Shortfall
├── stress.py           # historical + hypothetical stress tests
├── decomposition.py    # portfolio-level risk decomposition
└── models.py           # typed output dataclasses (no ORM here)
```

**Rule:** `risk/` is pure Python — no DB access, no HTTP calls, no FastAPI imports.
All functions take plain Python types / numpy arrays / dataclasses and return dataclasses.
This makes them trivially unit-testable.

---

## Return Series

All VaR methods operate on a **log-return series** (preferred) or simple returns.
Always use log returns for consistency:

```python
# backend/app/risk/returns.py

import numpy as np
import pandas as pd


def log_returns(prices: pd.Series) -> pd.Series:
    """Compute daily log returns from a price series."""
    return np.log(prices / prices.shift(1)).dropna()


def scale_to_horizon(one_day_var: float, horizon_days: int) -> float:
    """
    Scale 1-day VaR to h-day VaR using square-root-of-time rule.
    Valid for parametric VaR under i.i.d. returns assumption.
    Reference: Basel III, Jorion (2006) p.108
    """
    return one_day_var * np.sqrt(horizon_days)
```

---

## VaR — Three Methods

### Output type (all methods return this)

```python
# backend/app/risk/models.py
from dataclasses import dataclass

@dataclass(frozen=True)
class VaRResult:
    method: str             # "historical" | "parametric" | "monte_carlo"
    confidence: float       # 0.95 or 0.99
    horizon_days: int       # 1 or 10
    var_brl: float          # positive number = maximum expected loss
    portfolio_value_brl: float
    var_pct: float          # var_brl / portfolio_value_brl
    n_observations: int
    data_quality_warning: str | None = None
```

### 1. Historical Simulation

```python
def historical_var(
    returns: np.ndarray,
    portfolio_value_brl: float,
    confidence: float = 0.95,
    horizon_days: int = 1,
) -> VaRResult:
    """
    Non-parametric VaR by ordering historical P&L.
    Reference: Jorion (2006) Ch. 5; Hull (2022) Ch. 22.

    Args:
        returns: 1-D array of daily log returns (e.g. 250 observations)
        portfolio_value_brl: current MTM value in BRL
        confidence: 0.95 or 0.99
        horizon_days: scaling horizon (sqrt-of-time if > 1)
    """
    pnl = returns * portfolio_value_brl
    var_1d = float(np.percentile(pnl, (1 - confidence) * 100))
    var_scaled = abs(var_1d) * np.sqrt(horizon_days)

    return VaRResult(
        method="historical",
        confidence=confidence,
        horizon_days=horizon_days,
        var_brl=var_scaled,
        portfolio_value_brl=portfolio_value_brl,
        var_pct=var_scaled / portfolio_value_brl,
        n_observations=len(returns),
    )
```

### 2. Parametric (Variance-Covariance)

```python
from scipy import stats

def parametric_var(
    returns: np.ndarray,
    portfolio_value_brl: float,
    confidence: float = 0.95,
    horizon_days: int = 1,
) -> VaRResult:
    """
    Parametric VaR assuming normally distributed returns.
    WARNING: Underestimates tail risk for fat-tailed commodities.
    Reference: Jorion (2006) Ch. 4; Hull (2022) §22.3.
    """
    mu = np.mean(returns)
    sigma = np.std(returns, ddof=1)
    z = stats.norm.ppf(1 - confidence)
    var_1d = abs((mu + z * sigma) * portfolio_value_brl)
    var_scaled = var_1d * np.sqrt(horizon_days)

    return VaRResult(
        method="parametric",
        confidence=confidence,
        horizon_days=horizon_days,
        var_brl=var_scaled,
        portfolio_value_brl=portfolio_value_brl,
        var_pct=var_scaled / portfolio_value_brl,
        n_observations=len(returns),
        data_quality_warning="Assumes normality — likely underestimates commodity tail risk",
    )
```

### 3. Monte Carlo (GBM)

```python
def monte_carlo_var(
    returns: np.ndarray,
    portfolio_value_brl: float,
    confidence: float = 0.95,
    horizon_days: int = 1,
    n_simulations: int = 10_000,
    seed: int | None = None,  # always pass from config.MC_SEED
) -> VaRResult:
    """
    Monte Carlo VaR via Geometric Brownian Motion.
    Drift and volatility estimated from historical returns.
    Reference: Jorion (2006) Ch. 12.

    IMPORTANT: always pass seed=settings.MC_SEED for reproducibility.
    """
    rng = np.random.default_rng(seed)  # use new-style Generator, not np.random.seed
    mu = np.mean(returns)
    sigma = np.std(returns, ddof=1)

    simulated_returns = rng.normal(mu, sigma, size=(n_simulations, horizon_days))
    simulated_pnl = portfolio_value_brl * (np.expm1(simulated_returns.sum(axis=1)))

    var = abs(float(np.percentile(simulated_pnl, (1 - confidence) * 100)))

    return VaRResult(
        method="monte_carlo",
        confidence=confidence,
        horizon_days=horizon_days,
        var_brl=var,
        portfolio_value_brl=portfolio_value_brl,
        var_pct=var / portfolio_value_brl,
        n_observations=n_simulations,
    )
```

---

## CVaR / Expected Shortfall

```python
@dataclass(frozen=True)
class CVaRResult:
    confidence: float
    horizon_days: int
    var_brl: float     # VaR at same confidence (reference point)
    cvar_brl: float    # ES = E[L | L > VaR]
    portfolio_value_brl: float
    cvar_pct: float
    n_tail_observations: int
    regulatory_note: str


def historical_cvar(
    returns: np.ndarray,
    portfolio_value_brl: float,
    confidence: float = 0.95,
    horizon_days: int = 1,
) -> CVaRResult:
    """
    Expected Shortfall (CVaR) — average loss beyond VaR threshold.

    Regulatory context: Basel III/IV (FRTB) mandates ES at 97.5% confidence
    as the primary capital metric, replacing VaR. ES better captures tail risk
    because it is sub-additive (VaR is not).

    Reference: BCBS (2016) FRTB §3; Jorion (2006) p.168; Rockafellar & Uryasev (2000).
    """
    pnl = returns * portfolio_value_brl
    var_threshold = np.percentile(pnl, (1 - confidence) * 100)
    tail_losses = pnl[pnl <= var_threshold]

    cvar_1d = abs(float(np.mean(tail_losses)))
    cvar_scaled = cvar_1d * np.sqrt(horizon_days)
    var_scaled = abs(var_threshold) * np.sqrt(horizon_days)

    return CVaRResult(
        confidence=confidence,
        horizon_days=horizon_days,
        var_brl=var_scaled,
        cvar_brl=cvar_scaled,
        portfolio_value_brl=portfolio_value_brl,
        cvar_pct=cvar_scaled / portfolio_value_brl,
        n_tail_observations=len(tail_losses),
        regulatory_note=(
            f"Basel III/IV FRTB uses ES at 97.5%. "
            f"This result at {confidence*100:.0f}% has {len(tail_losses)} tail obs."
        ),
    )
```

---

## Stress Testing

See `references/stress_scenarios.md` for the full scenario table.

```python
@dataclass(frozen=True)
class StressResult:
    scenario_name: str
    scenario_type: str       # "historical" | "hypothetical"
    soja_shock_pct: float
    milho_shock_pct: float
    fx_shock_pct: float
    pnl_brl: float
    pnl_pct_portfolio: float
    worst_position_id: str | None


def apply_stress(
    positions: list[dict],
    current_prices: dict,   # {"soja_cbot": float, "milho_cbot": float, "fx": float}
    scenario: dict,         # from STRESS_SCENARIOS constant
) -> StressResult:
    """
    Apply percentage shocks to current market prices and recompute MTM.
    Shocks are multiplicative: shocked_price = current × (1 + shock_pct/100)
    """
    ...
```

**Rule:** Shocks are always **multiplicative**, never additive.
`shocked_cbot = current_cbot × (1 + shock / 100)`

---

## API Response Shape

```python
# backend/app/api/v1/risk.py response model

class RiskSummaryResponse(BaseModel):
    as_of: date
    portfolio_value_brl: float
    var: dict[str, VaRResult]   # keys: "historical_95", "historical_99", "parametric_95", "mc_95"
    cvar: dict[str, CVaRResult]
    stress: list[StressResult]
    data_quality_warnings: list[str]
    methodology_refs: list[str]   # always include literature refs in the response
```

Always include `methodology_refs` in the response — this surfaces in the UI's
collapsible methodology panels and is a differentiator of this project.

---

## Testing Requirements

Every function in `risk/` must have:

```python
# tests/unit/risk/test_var.py

def test_historical_var_95_less_than_99():
    """VaR at 99% must be >= VaR at 95% for the same data."""
    ...

def test_monte_carlo_reproducible_with_seed():
    """Same seed must produce identical results across runs."""
    r1 = monte_carlo_var(returns, 1_000_000, seed=42)
    r2 = monte_carlo_var(returns, 1_000_000, seed=42)
    assert r1.var_brl == r2.var_brl

def test_cvar_always_greater_than_var():
    """CVaR >= VaR at same confidence level by definition."""
    ...

def test_parametric_var_has_warning():
    """Parametric VaR must always carry normality warning."""
    result = parametric_var(...)
    assert result.data_quality_warning is not None
```
