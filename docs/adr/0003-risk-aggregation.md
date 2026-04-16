# ADR-0003: Risk aggregation — flat and per-leg VaR methodology

**Status:** Accepted
**Date:** 2026-04-16
**Deciders:** Diego Rossi (owner)

## Context

The portfolio's P&L is driven by three independent risk factors:

- **CBOT** (USc/bu) — the exchange futures price for the underlying commodity.
- **Basis / Prêmio** (USD/bu) — the premium over CBOT for Brazilian origin/delivery.
- **FX** (BRL/USD) — the currency conversion rate.

Every physical position, once its legs are (partially or fully) open, has exposure to all three. Derivatives have exposure to a subset: CBOT derivatives to CBOT, basis forwards to basis, FX derivatives to FX. The aggregated portfolio has a net exposure on each leg, and that net exposure translates to a BRL P&L sensitivity per unit move of the corresponding factor.

Two risk views serve different purposes:

1. **Flat VaR / total portfolio VaR** — the 1-number view. Answers "what is our worst expected BRL loss at confidence α over horizon h?" This is the capital reserve / stop-loss perspective. It accounts for correlations between the three factors (e.g., historically, a CBOT down-move often co-occurs with a BRL weakening — partially offsetting for a long Brazilian producer).

2. **Per-leg VaR** — the decomposition view. Computes VaR *independently* on each factor's contribution to portfolio P&L. Answers "how much of the risk comes from CBOT vs basis vs FX?" This is the hedging perspective — it tells you where to rebalance.

These two views are **not additive**: `VaR_flat ≤ VaR_cbot + VaR_basis + VaR_fx` in general, with equality only under perfect positive correlation (which never happens). The gap is the "diversification benefit" — a real effect, not a methodology error.

The original `CLAUDE.md` only specified flat VaR. The expanded scope (per the user's answers on derivatives as standalone instruments and insight level "complete") demands both views so that a user entering a standalone FX hedge can see precisely which leg was neutralized.

## Decision

Compute both flat and per-leg VaR for every method (historical, parametric, Monte Carlo), and surface them side-by-side in the UI. Attribution (Phase 7) provides position-level contribution to flat VaR via the component-VaR decomposition.

Specifically:

- **Flat VaR** — apply the chosen method (historical percentile / parametric formula / Monte Carlo path) to the time series of portfolio daily P&L built by revaluing the full aggregate exposure at each historical factor tuple `(cbot, basis, fx)`.
- **Per-leg VaR** — apply the same method, but independently to three univariate time series: leg P&L attributed to CBOT moves only (holding basis and FX flat at current values), same for basis, same for FX.
- **Component VaR (attribution, Phase 7)** — decompose flat VaR into position-level contributions using `c_i = ρ_{i,p} × σ_i × w_i × VaR_p / σ_p` for the parametric case; for historical/MC, bootstrap the same formula off the simulated/observed returns. The sum of component VaRs equals flat VaR by construction.

Parametric VaR uses the standard formula `VaR = z_α × σ_P × sqrt(h)` with `σ_P` computed from the factor covariance matrix `Σ` and the portfolio factor weights `w`: `σ_P = sqrt(w' Σ w)`. Monte Carlo uses Cholesky-correlated GBM on the three factors with `n_paths = 10_000` and `seed = config.MC_SEED` for reproducibility.

## Options Considered

### Option A — Compute both, flat as primary + per-leg as decomposition (chosen)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Medium — 2× compute (flat + 3 per-leg) but same method reused |
| Cost | Low — sub-second for typical portfolio sizes at N=10k MC paths |
| Scalability | Good — all three methods vectorize on numpy |
| Methodological rigor | High — matches industry practice (FRTB requires both total and sensitivity-based views) |
| UI value | High — per-leg view answers "where do I hedge?" directly |

**Pros:**
- Covers both capital-reserve use case and hedge-allocation use case.
- Component VaR lets us rank individual positions by risk contribution — a standout portfolio feature.
- Aligns with Basel III/IV FRTB framework which requires both total ES and sensitivity-based capital.
- Per-leg and attribution share inputs (factor returns, exposures) with flat — no redundant computation.

**Cons:**
- Must explicitly document to users that flat VaR ≤ sum(per-leg VaRs) — otherwise the arithmetic looks wrong.
- Numerical validation: components must sum to flat within a tolerance (property test in Phase 7).
- For nonlinear instruments (options), per-leg VaR requires either (a) delta-approximation per leg at the current spot — fast, simpler, slightly off for large moves, or (b) full revaluation per path — slower but exact. MVP uses (a); Phase 8 adds (b) as an option.

### Option B — Flat VaR only

| Dimension | Assessment |
|-----------|------------|
| Complexity | Low |
| Cost | Lowest |
| Scalability | Best |
| Methodological rigor | Meets the single-number threshold |
| UI value | Lower — doesn't answer "where is the risk coming from" |

**Pros:**
- Simplest implementation and UI.
- Enough to tick the "has VaR" box.

**Cons:**
- Doesn't answer the primary operational question for a hedger: which leg is driving my VaR?
- Makes attribution (Phase 7) much harder to motivate — component VaR needs a base flat VaR but the per-leg sanity-check is gone.
- Weakens the portfolio demo — recruiters in the commodities space know per-leg decomposition is standard; absence is conspicuous.

### Option C — Per-leg VaR only, client-side sum

| Dimension | Assessment |
|-----------|------------|
| Complexity | Low backend |
| Cost | Low |
| Scalability | Good |
| Methodological rigor | Poor — summing per-leg VaRs over-states total risk |
| UI value | High per-leg, wrong aggregate |

**Pros:**
- Simple to implement.

**Cons:**
- Summing per-leg VaRs ignores diversification — the resulting number is mechanically wrong as an estimate of portfolio loss at confidence α.
- Would need to be explicitly labeled "undiversified total" — creates confusion.
- Directly undermines the capital-reserve use case.

## Trade-off Analysis

The crux is whether to spend the incremental engineering on computing both flat and per-leg. The answer is yes, for three reasons:

1. **Domain fit** — the user base this platform is modeled on (agribusiness risk managers, hedgers, traders) thinks in legs. A tool that presents only a flat number is one abstraction level above where their decisions happen.
2. **Methodological honesty** — reporting per-leg without flat (Option C) produces a wrong portfolio number; reporting flat without per-leg (Option B) hides useful signal. The two together tell an honest, complete story.
3. **Attribution lifts off per-leg** — Phase 7's component VaR ranking of positions only makes sense when we already have the factor decomposition plumbing in place. Skipping it in MVP means partially redoing it later.

The nonlinear-instrument concern (options revaluation in per-leg view) is real but bounded: for MVP (linear derivatives only), delta-approximation is exact. Phase 8 options pricing adds the choice between fast delta-approx and full revaluation — a configurable trade-off, not a methodology change.

## Consequences

**What becomes easier:**
- UI surfaces "Total VaR" + three sub-numbers ("CBOT contribution", "Basis contribution", "FX contribution") with a note that they don't sum due to correlation.
- Component VaR (Phase 7) plugs in naturally — it decomposes flat VaR along positions, using the same factor return series.
- Hedge-ratio math: "to neutralize CBOT leg, I need X contracts of ZS=F" is derivable directly from the per-leg exposure table.
- FRTB-style documentation: the risk methodology doc can cite Basel III/IV frameworks cleanly.

**What becomes harder:**
- Must prominently document (in `docs/RISK_METHODOLOGY.md` and inline UI tooltips) that `VaR_flat ≤ Σ VaR_leg` in general, and explain diversification benefit.
- Testing: need property tests for both views — parametric closed-form sanity for each leg, MC reproducibility across both, historical percentile equivalence.
- Caching strategy is more nuanced — stale flat VaR is OK if per-leg hasn't moved; must key cache by `(user_id, method, confidence, horizon, view)`.
- Confidence-level consistency: UI must prevent mixing e.g. 95% flat with 99% per-leg in the same report.

**What we'll need to revisit:**
- If the platform adds cross-commodity spread trades (long soja / short milho), the factor model should split CBOT into `cbot_soja` and `cbot_milho` (which it already does in the Phase 7 correlation matrix) and VaR views extend naturally.
- If options become a meaningful share of portfolio Greeks, decide whether per-leg VaR should use full revaluation (slower, exact) instead of delta-approximation (fast, linearized).
- If backtesting reveals systematic under- or over-estimation of flat VaR under historical method, consider exponentially-weighted volatility estimates or Filtered Historical Simulation (Barone-Adesi).

## Action Items

1. [x] Phase 6: implement `historical_var`, `parametric_var`, `monte_carlo_var` in `app/risk/var.py` with both flat and per-leg outputs, returning `VaRResult(method, confidence, horizon_days, value_brl, per_leg={cbot, basis, fx})`.
2. [x] Phase 6: unit tests verify (a) parametric per-leg sums ≤ flat + tolerance on correlated synthetic data, (b) MC reproducibility with seed, (c) √h scaling for parametric.
3. [x] Phase 7: implement `component_var` in `app/risk/attribution.py` with property test `sum(components) ≈ flat_VaR ± 1%`.
4. [x] Phase 7: Cholesky-correlated MC in `app/risk/mc.py` to support fan-chart and ES per-leg.
5. [ ] Phase 11: risk dashboard UI shows flat VaR prominently with per-leg breakdown in a subordinate card + tooltip explaining diversification benefit.
6. [ ] Phase 11: include literature citation (Jorion 2006 Ch. 7, Hull 2022 Ch. 22, Basel III/IV FRTB) in the methodology tooltip.
