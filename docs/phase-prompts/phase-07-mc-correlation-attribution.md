# Phase 7 — Risk engine: MC fan chart + correlation + VaR attribution

> Paste-load: read this file end-to-end, execute every section. Bypass mode is assumed active.

## Context

Phase 7 extends the risk engine with three advanced analytics built on top of Phase 6:

1. **Cholesky-correlated Monte Carlo path simulation** — proper geometric Brownian motion over the 3-factor space (CBOT, basis, FX, split per commodity where applicable). Drives the **fan chart** output (percentile bands of portfolio P&L over horizon).
2. **Correlation matrix endpoint** — exposes the empirical factor correlation matrix with a PSD guard (nearest-PSD if the raw covariance isn't positive semi-definite).
3. **Component VaR / attribution** — decomposes the flat VaR into position-level contributions. Property: `Σ components == flat VaR` within rounding.

Phase 6 delivered the basic (uncorrelated) MC path. Phase 7 replaces that with correlated paths, adds fan chart, correlation matrix, and attribution endpoints.

Reference:
- `CLAUDE.md` — Risk Metrics: Monte Carlo + attribution rows.
- `docs/adr/0003-risk-aggregation.md` — per-leg / flat methodology.
- `.claude/skills/risk-engine-patterns/SKILL.md` — Cholesky / PSD guard / reproducibility contract.

## Running mode

`--dangerously-skip-permissions` active. Commit + push to main on validation success.

## Tasks

### 1. Correlation module

`backend/app/risk/correlation.py`:

- `def correlation_matrix(returns: pd.DataFrame) -> tuple[np.ndarray, list[str]]`
  - Inputs: DataFrame with 1 column per factor, rows = daily returns (from `risk.returns.compute_returns`).
  - Outputs: a `(N, N)` numpy array (N = number of factors) + the list of factor names in matrix row/column order.
  - Compute via `np.corrcoef`.
- `def nearest_psd(matrix: np.ndarray, eps: float = 1e-8) -> np.ndarray`
  - Force a (near-)correlation matrix to be positive semi-definite by clipping negative eigenvalues to `eps`.
  - Used when the empirical covariance has numerical drift that breaks Cholesky.
- `def cholesky_factor(corr: np.ndarray) -> np.ndarray`
  - Return L such that `L @ L.T ≈ corr`. Call `nearest_psd` first if `np.linalg.cholesky` raises.
- All functions fully typed, docstringed, with pure-function semantics (no I/O).

### 2. Correlated MC paths (`backend/app/risk/mc.py`)

Replace the `monte_carlo_var` path's uncorrelated RNG with a Cholesky-correlated sampler:

- `def simulate_correlated_paths(mu: np.ndarray, sigma: np.ndarray, corr: np.ndarray, n_paths: int, n_steps: int, dt: float, seed: int | None) -> np.ndarray`
  - `mu: (N,)` — per-factor drift (can be zero for VaR use)
  - `sigma: (N,)` — per-factor volatility (annualized or daily; consistent with `dt`)
  - `corr: (N, N)` — factor correlation
  - Output shape: `(n_paths, n_steps, N)` — continuous GBM multiplicative process:
    `S_t+1 = S_t * exp((mu - 0.5*sigma²)*dt + sigma*sqrt(dt)*L @ Z_t)`
    where `L = cholesky(corr)` and `Z_t ~ N(0, I)` per step.
  - Use `np.random.default_rng(seed)` for full reproducibility.
- `def fan_chart_paths(exposure: AggregateExposure, returns: pd.DataFrame, horizon_days: int = 10, n_paths: int = 10_000, seed: int | None = None) -> FanChartResult`
  - Applies `simulate_correlated_paths` to the factor set, converts paths to portfolio P&L series (multiply weighted returns per path per step), then returns percentiles `[5, 25, 50, 75, 95]` at each day from `t=1` to `t=horizon_days`.
  - Output: `FanChartResult` dataclass with `percentiles: dict[int, list[Decimal]]` (key = percentile, value = list of `horizon_days` values), `horizon_days: int`, `n_paths: int`, `seed: int`.

### 3. Attribution (`backend/app/risk/attribution.py`)

- `def component_var(positions: list[PositionWeight], returns: pd.DataFrame, confidence: Decimal = Decimal("0.95"), horizon_days: int = 1, method: Literal["parametric"] = "parametric") -> list[PositionContribution]`
  - `PositionWeight` dataclass: `position_id: UUID`, `label: str`, `weight_brl: Decimal` (signed — long positive, short negative), `factor_exposures: dict[str, Decimal]` (mapping from factor name → BRL exposure).
  - Parametric component formula: `c_i = (w_i × σ_i × ρ_{i,p}) × VaR_p / σ_p` where `ρ_{i,p} = cov(r_i, r_p) / (σ_i × σ_p)`.
  - Output: `list[PositionContribution(position_id, label, contribution_brl, share_pct)]` sorted desc by `contribution_brl`.
- `def marginal_var(position: PositionWeight, portfolio: list[PositionWeight], returns: pd.DataFrame, shift_pct: Decimal = Decimal("0.01"), confidence: Decimal = Decimal("0.95")) -> Decimal`
  - Computes ∆VaR from shifting `position.weight_brl` by `shift_pct * abs(weight)`.
  - Returns `Decimal` (BRL change in flat VaR).
- Types in `risk/types.py`: add `PositionWeight`, `PositionContribution`, `FanChartResult`.

### 4. API endpoints (`backend/app/api/v1/risk.py` extension)

Add three routes mounted on the existing `/risk` router:

- `POST /risk/mc/fan`:
  - Body: `{weights: dict[str, Decimal], horizon_days: int = 10, n_paths: int = 10000, seed: int | None}`
  - Calls `fan_chart_paths`.
  - Returns `FanChartResult` (as dict with percentiles + metadata).
- `GET /risk/correlation`:
  - Query: `window: int = 252` (rows of history to use).
  - Loads last `window` returns from `prices`, computes correlation matrix, returns `{matrix: list[list[float]], names: list[str]}`.
- `POST /risk/attribution`:
  - Body: `{positions: list[PositionWeightIn], confidence, horizon_days}`.
  - Returns `list[PositionContributionOut]` sorted desc.

All 3 endpoints require `Depends(get_current_user)` (auth gated). Log structured with `method`, `n_paths`, `window` context keys.

### 5. Unit tests

`backend/tests/unit/risk/test_correlation.py`:

- `test_correlation_matrix_known_inputs`: two perfectly correlated factors → ρ ≈ 1.0; two orthogonal factors → ρ ≈ 0.
- `test_nearest_psd_fixes_tiny_negative_eigenvalue`: input with one slightly negative eigenvalue (e.g. `-1e-10`) produces a PSD output while preserving structure.
- `test_cholesky_roundtrip`: for a known PSD matrix, `L @ L.T ≈ corr` within `1e-10`.

`backend/tests/unit/risk/test_mc.py`:

- `test_simulate_paths_shape`: output shape `(n_paths, n_steps, N)`.
- `test_mc_reproducibility`: same seed → same array (bit-exact via `np.array_equal`).
- `test_correlated_paths_preserve_correlation`: generated paths' empirical correlation matches input `corr` within `0.05` at `n_paths=50k`.
- `test_fan_chart_percentiles_monotone`: at every time step, `p5 ≤ p25 ≤ p50 ≤ p75 ≤ p95`.
- `test_fan_chart_reproducibility`: same seed → same percentiles list.

`backend/tests/unit/risk/test_attribution.py`:

- `test_component_var_sums_to_flat`: on a synthetic 5-position portfolio, `Σ c_i ≈ flat_VaR` within `1%`.
- `test_component_var_ordering`: output is sorted by `contribution_brl` desc.
- `test_marginal_var_positive_shift_increases_var`: for a long-only portfolio, increasing a position's weight should increase VaR.
- Property test: `share_pct` column sums to `~100%`.

### 6. Fixture updates

`backend/tests/fixtures/price_history.py` already has `iid_normal_returns` and `correlated_normal_returns`. Extend if needed for Phase 7 (specifically `correlated_normal_returns` with configurable correlation matrix + factor names).

## Constraints

- MC sampling MUST accept and honor an explicit `seed` parameter, falling back to `settings.MC_SEED` if none passed.
- No `float` at the API boundary — `Decimal` in/out.
- Internal numpy compute in `float64` is fine; convert back to `Decimal` at the boundary.
- Coverage on `app.risk/` must stay ≥90% (will likely rise to ~99%).
- NO new dependencies required. `numpy`, `pandas`, `scipy` are already in the project (`scipy` is used for statistical helpers if needed).
- Cholesky PSD guard: if `np.linalg.cholesky` raises `LinAlgError`, fall back to `nearest_psd(corr)` and retry. Log a structured warning when that path triggers.

## MANDATORY validation

Run in this order, capture output:

1. `cd backend && uv run mypy app/risk --strict`  → 0 errors
2. `cd backend && uv run ruff check app tests`  → clean
3. `cd backend && uv run pytest tests/unit/risk/ -v --cov=app.risk --cov-report=term-missing`  → all pass, coverage ≥90%
4. `cd backend && uv run pytest tests/unit/risk/test_correlation.py tests/unit/risk/test_mc.py tests/unit/risk/test_attribution.py -v`  → all new tests pass (12+)
5. `cd backend && uv run python -c "
import asyncio
from httpx import AsyncClient
from app.main import app
async def smoke():
    async with AsyncClient(app=app, base_url='http://testserver') as c:
        for path in ['/api/v1/risk/mc/fan', '/api/v1/risk/correlation', '/api/v1/risk/attribution']:
            method = 'GET' if path.endswith('correlation') else 'POST'
            r = await c.request(method, path, json={} if method == 'POST' else None)
            assert r.status_code == 401, f'{path} returned {r.status_code}, expected 401 (auth required)'
        print('3 new risk endpoints auth-gated (401 without JWT)')
asyncio.run(smoke())
"`  → prints ok message

6. `cd backend && uv run python -c "
from decimal import Decimal
import numpy as np
from app.risk.correlation import correlation_matrix, nearest_psd, cholesky_factor
import pandas as pd
rng = np.random.default_rng(42)
N = 5
R = rng.normal(0, 0.01, (2000, N))
df = pd.DataFrame(R, columns=[f'f{i}' for i in range(N)])
corr, names = correlation_matrix(df)
print('corr shape:', corr.shape)
print('diagonal (should be ~1):', np.diag(corr).tolist())
L = cholesky_factor(corr)
print('cholesky L.shape:', L.shape)
print('reconstructed close to corr:', np.allclose(L @ L.T, corr, atol=1e-10))
"`  → prints correct shapes + True

Invariants:
- [ ] mypy strict: 0 errors on app/risk
- [ ] Coverage on `app.risk/` ≥ 90% (expect ~99%)
- [ ] 12+ new unit tests across correlation/mc/attribution all pass
- [ ] MC reproducibility verified with explicit seed
- [ ] Correlation matrix diagonal is all ~1.0
- [ ] Cholesky roundtrip is within `1e-10`
- [ ] Component VaR sums to flat VaR within 1%
- [ ] `share_pct` column sums to ~100%
- [ ] 3 new endpoints auth-gated (return 401 without JWT)
- [ ] No `float` at any Pydantic boundary

## Commit + push

```bash
git add -A
git status --short
git commit -m "feat(risk): Phase 7 — Cholesky MC fan chart + correlation + component VaR

- risk/correlation.py: empirical correlation matrix, nearest_psd guard, cholesky factor
- risk/mc.py: Cholesky-correlated GBM path simulator (replaces Phase 6 uncorrelated sampler)
- risk/attribution.py: component VaR (parametric formula) + marginal VaR by weight shift
- api/v1/risk.py: 3 new endpoints (POST /mc/fan, GET /correlation, POST /attribution)
- risk/types.py: PositionWeight, PositionContribution, FanChartResult
- 12+ new unit tests with property checks (sum-to-flat, PSD guard, reproducibility)
- Coverage on app.risk/ raised to ~99%

Deferred: integration with live positions table (Phase 7 uses explicit weights in body,
mirroring Phase 6's pragmatic design). Auto-derivation will hook here in Phase 11 dashboard.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin main
```

## COWORK HANDOFF

```
=== COWORK HANDOFF — PHASE 7 BEGIN ===

Status: <✅ shipped / ❌ failed>
Mode:   --dangerously-skip-permissions
Date:   <YYYY-MM-DD HH:MM local>

Git state (post-commit):
  branch:       main
  local HEAD:   <sha>
  origin/main:  <sha>
  aligned:      <yes/no>
  tree clean:   <yes/no>

Commit (if shipped):
  SHA:     <sha>
  subject: feat(risk): Phase 7 — Cholesky MC fan chart + correlation + component VaR
  push:    <paste the "To ... main -> main" line>

Validation matrix:
  [✓/✗] 1. mypy strict app/risk        <N source files, 0 errors>
  [✓/✗] 2. ruff                         <clean>
  [✓/✗] 3. pytest + coverage            <N/N passed, coverage=XX%>
  [✓/✗] 4. new unit tests (correlation/mc/attribution) <N/N passed>
  [✓/✗] 5. new endpoints auth smoke     <3/3 return 401 without JWT>
  [✓/✗] 6. correlation + cholesky math  <shape OK, diagonal ~1, roundtrip True>

Sample results (paste verbatim from test runs):
  correlation diagonal (5 factors):    <[values]>
  cholesky roundtrip max diff:          <value>
  component_var sum vs flat_var:        sum=<value>, flat=<value>, err=<pct>
  fan chart percentiles at t=10:        p5=<value>, p50=<value>, p95=<value>
  MC reproducibility (seed=42, 2 runs): <True/False, bit-exact>

Files created:
  backend/app/risk/:          correlation.py, mc.py, attribution.py
  backend/app/api/v1/:        risk.py (extended: /mc/fan, /correlation, /attribution)
  backend/app/risk/types.py   (PositionWeight, PositionContribution, FanChartResult added)
  backend/tests/unit/risk/:   test_correlation.py (N), test_mc.py (N), test_attribution.py (N)

Blockers / errors (if ❌):
  <step number>: <last 20 lines of command output>
  hypothesis: <your best guess at cause>
  scope-of-fix: <within prompt scope / requires Diego>

Next expected action (Diego):
  - Open http://localhost:8000/api/v1/docs, authenticate, call GET /risk/correlation?window=252;
    confirm 5×5 matrix with diagonal 1.0, symmetric off-diagonal.
  - Call POST /risk/mc/fan; expect 5 arrays of horizon_days length, all monotone across percentiles.
  - Call POST /risk/attribution with a toy 3-position portfolio; sum of share_pct ≈ 100.
  - Return to Cowork for Phase 8 (options pricing, ADVANCED) or skip to Phase 9 (frontend scaffold).

Open questions for Diego:
  <list or "none">

=== COWORK HANDOFF — PHASE 7 END ===
```
