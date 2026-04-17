# Risk Methodology Reference

## Purpose

This document defines the methodology used for all risk calculations in the
commodity-risk-dashboard. Include these references in API responses and UI
methodology panels. Claude should cite these sources whenever explaining or
implementing risk calculations.

---

## Value at Risk (VaR)

### Definition

VaR(α, h) = the minimum loss not exceeded with probability α over horizon h.
Equivalently: the loss exceeded only (1−α)×100% of the time.

A 1-day 95% VaR of BRL 50,000 means: there is a 5% chance of losing more than
BRL 50,000 in a single day.

### Method 1: Historical Simulation

- Compute daily log returns from the last N trading days (default: 250 = ~1 year)
- Scale to portfolio P&L: P&L_t = r_t × V
- Sort P&L from worst to best
- VaR = |percentile at (1−α) × 100|
- Scale to h days: VaR_h = VaR_1 × √h (square-root-of-time rule)

**Advantages:** No distributional assumption, captures fat tails and skewness.
**Limitations:** Assumes past returns are representative of future; 250 obs may miss
  tail events; does not capture structural breaks.

**References:**
- Jorion, P. (2006). *Value at Risk: The New Benchmark for Managing Financial Risk*, 3rd ed. McGraw-Hill. Ch. 5.
- Hull, J.C. (2022). *Options, Futures, and Other Derivatives*, 11th ed. Pearson. Ch. 22.

### Method 2: Parametric (Variance-Covariance)

Assumes normally distributed returns:

```
VaR(α) = |μ_p + z_α × σ_p| × V
```

Where:
- μ_p = mean daily portfolio return
- σ_p = standard deviation of daily portfolio return
- z_α = standard normal quantile (z_0.95 = −1.645, z_0.99 = −2.326)
- V = portfolio value

**Advantages:** Simple, fast, analytical.
**Limitations:** Normality assumption fails for commodities (fat tails, skewness).
  Consistently underestimates extreme losses. Always flag with normality warning.

**References:**
- Jorion (2006) Ch. 4.
- RiskMetrics Technical Document (1996). J.P. Morgan/Reuters.

### Method 3: Monte Carlo Simulation

1. Estimate drift (μ) and volatility (σ) from historical returns
2. Simulate N paths of GBM: S_t = S_0 × exp((μ − σ²/2)t + σ√t × Z), Z ~ N(0,1)
3. Compute portfolio P&L for each path
4. VaR = percentile at (1−α) of simulated P&L distribution

Default: N = 10,000 simulations, seed-controlled for reproducibility.

**Advantages:** Flexible distributional assumptions, handles non-linear instruments.
**Limitations:** Results depend on GBM assumptions; computationally heavier.

**References:**
- Jorion (2006) Ch. 12.
- Glasserman, P. (2003). *Monte Carlo Methods in Financial Engineering*. Springer.

---

## CVaR / Expected Shortfall (ES)

```
ES_α = E[L | L > VaR_α] = (1/(1−α)) × ∫_{VaR_α}^{∞} l f(l) dl
```

In discrete (historical) form:
```
ES_α = mean of all losses exceeding VaR_α
```

### Regulatory Context

Basel III/IV (Fundamental Review of the Trading Book, FRTB) **replaces VaR with
ES at 97.5% confidence** as the primary capital metric because:

1. ES is sub-additive (satisfies diversification principle); VaR is not
2. ES penalizes severity of tail losses, not just frequency
3. ES at 97.5% ≈ VaR at 99% in terms of capital requirement level

**For portfolio comparison:**
- ES(97.5%) ≈ ES(95%) × 1.2 to 1.5 (depends on tail shape)
- ES is always ≥ VaR at the same confidence level

**References:**
- Basel Committee on Banking Supervision (2016). *Minimum Capital Requirements for Market Risk (FRTB)*. January 2016.
- Rockafellar, R.T. and Uryasev, S. (2000). "Optimization of Conditional Value-at-Risk." *Journal of Risk*, 2(3), 21–42.
- Artzner, P. et al. (1999). "Coherent Measures of Risk." *Mathematical Finance*, 9(3), 203–228.

---

## Stress Testing

### Rationale

VaR and CVaR are calibrated on recent historical distributions.
They fail to capture structural breaks, geopolitical shocks, or
once-in-a-decade events that lie outside the calibration window.
Stress testing complements VaR by asking: "what if the market does X?"

### Methodology

- **Historical scenarios:** replay shocks from specific crisis periods
  (prices, FX, correlations are taken from that period)
- **Hypothetical scenarios:** user-defined simultaneous shocks across factors
- All shocks are **multiplicative**: P_shocked = P_current × (1 + shock%)

### Interpretation for Long Commodity Positions

Long positions in soja/milho:
- Benefit from price increases (positive commodity shock)
- Benefit from BRL depreciation (positive FX shock, because revenue in BRL goes up)
- Are hurt by commodity price drops
- Have partial FX offset: a commodity drop in USD may be partially offset by BRL
  depreciation — this is the key structural feature of Brazilian agro exports

**References:**
- Jorion (2006) Ch. 14: "Stress Testing."
- BCBS (2009). *Principles for Sound Stress Testing Practices and Supervision*.
- IMF (2012). *Macrofinancial Stress Testing: Principles and Practices*.
- CONAB. *Acompanhamento da Safra Brasileira de Grãos*. (context for supply shocks)

---

## Square-Root-of-Time Scaling

For scaling 1-day VaR to h-day VaR:
```
VaR_h = VaR_1 × √h
```

**Assumptions required:**
1. Returns are i.i.d. (no autocorrelation)
2. No intraday position changes

**Basel III usage:** 10-day VaR = 1-day VaR × √10 (used for market risk capital)

This is an approximation. For commodity markets with strong mean reversion or
momentum, the true h-day VaR may diverge from the scaled estimate.

---

## Unit Conventions (Brazil Agro)

| Measure | Unit | Notes |
|---|---|---|
| CBOT soja | USc/bushel | Divide by 100 for USD/bu |
| CBOT milho | USc/bushel | Divide by 100 for USD/bu |
| B3 milho | BRL/saca (60kg) | 1 ton = 16.667 sacas |
| Physical | BRL/ton | End-user reference unit |
| 1 ton soja | 36.744 bushels | Standard conversion |
| 1 ton milho | 56.0 bushels | Standard conversion |
| FX | BRL/USD | "Dólar" in Brazil = BRL per 1 USD |
