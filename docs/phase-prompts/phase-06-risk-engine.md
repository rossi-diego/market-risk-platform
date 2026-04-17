# Phase 6 — Risk engine: VaR + CVaR + stress (flat + per-leg)

> Paste-load: read this file end-to-end, execute every section. Bypass mode is assumed active.

## Context

Phase 6 implements the 3 VaR methodologies (historical, parametric, Monte Carlo basic), Expected Shortfall, and stress testing (historical + custom). Every metric computes a flat view AND a per-leg breakdown (CBOT, basis, FX). Methodology reference: `docs/adr/0003-risk-aggregation.md`.

Reference:
- `CLAUDE.md` — Risk Metrics Methodology Reference.
- `.claude/skills/risk-engine-patterns/SKILL.md` (seed discipline, typed outputs, literature).
- `.claude/skills/risk-engine-patterns/references/stress_scenarios.md` (historical shock table).
- `docs/adr/0003-risk-aggregation.md`.

Advanced MC + correlation + component VaR are Phase 7 — this phase delivers the basic MC and flat attribution stubs.

## Running mode

`--dangerously-skip-permissions` active. Commit + push to main on validation success.

## Tasks

### 1. Return series builders (`backend/app/risk/returns.py`)

- `def compute_returns(prices_df: pd.DataFrame, kind: Literal["log","simple"] = "log") -> pd.DataFrame`:
  - Expects a DataFrame indexed by `observed_at` with columns = instrument names (ZS=F, ZC=F, USDBRL=X).
  - Returns same shape with first row dropped.
- `def align_multi_series(series_by_instrument: dict[str, pd.Series]) -> pd.DataFrame`:
  - Outer join on timestamps, forward-fill up to 1 business day gap, drop leading NaNs.
- `def rolling_window(df: pd.DataFrame, days: int = 252) -> pd.DataFrame`:
  - Tail N rows; raise `ValueError` if insufficient history.

### 2. VaR engine (`backend/app/risk/var.py`)

Result types in `backend/app/risk/types.py` (extend existing file):

```python
@dataclass(frozen=True, slots=True)
class VaRResult:
    method: Literal["historical", "parametric", "monte_carlo"]
    confidence: Decimal               # 0.95, 0.975, 0.99
    horizon_days: int                  # 1, 5, 10
    value_brl: Decimal                 # flat VaR, positive number (magnitude of worst-case loss)
    per_leg: dict[Literal["cbot","basis","fx"], Decimal]  # per-leg VaRs, also positive
    n_observations: int                # size of sample used
    seed: int | None                   # MC only
```

Functions (all type-hinted, docstringed):

- `def historical_var(returns: pd.DataFrame, weights: dict[str, Decimal], confidence: Decimal = Decimal("0.95"), horizon_days: int = 1, window: int = 252) -> VaRResult`
  - Build portfolio P&L series = Σ (weights[instrument] × returns[instrument]) × portfolio_value_brl.
  - Scale for horizon: either use overlapping `h`-day returns OR scale single-day percentile by √h (pick overlapping; more accurate for historical).
  - Flat: percentile at (1 - confidence) of P&L distribution, absolute value.
  - Per-leg: compute the same but with weights zeroed out except for the one leg at a time.
- `def parametric_var(returns: pd.DataFrame, weights: dict[str, Decimal], confidence: Decimal = Decimal("0.95"), horizon_days: int = 1) -> VaRResult`
  - Compute covariance matrix Σ of returns.
  - Portfolio variance σ²_P = w' Σ w (mind dtype — convert weights via `np.asarray([Decimal(...)])` then `float`; Decimal not natively in numpy).
  - VaR_flat = z_α × σ_P × sqrt(horizon) × portfolio_value.
  - Per-leg VaR: use each leg's univariate σ × z × sqrt(h) × weight.
  - Note: `sum(per_leg) ≥ flat` always (diversification) — document this in the docstring.
- `def monte_carlo_var(returns: pd.DataFrame, weights: dict[str, Decimal], confidence: Decimal = Decimal("0.95"), horizon_days: int = 1, n_paths: int = 10_000, seed: int | None = None) -> VaRResult`
  - Use `np.random.default_rng(seed or settings.MC_SEED)`.
  - Sample from multivariate normal with mean + covariance from historical returns (same assumption as parametric — this is "basic" MC; Phase 7 adds Cholesky-correlated GBM).
  - Simulate N paths of `horizon_days` steps.
  - Apply weights, get P&L distribution at horizon end.
  - Percentile at (1 - confidence).
  - Per-leg: reuse sampled paths but zero out non-leg weights.

### 3. CVaR / Expected Shortfall (`backend/app/risk/cvar.py`)

- `def expected_shortfall(returns: pd.DataFrame, weights: dict[str, Decimal], confidence: Decimal = Decimal("0.975"), horizon_days: int = 1, method: Literal["historical","parametric","monte_carlo"] = "historical") -> CVaRResult`:
  - Historical: mean of P&L values ≤ percentile at (1 - confidence).
  - Parametric: closed form `φ(z) / (1 - α) × σ_P × sqrt(h)` where `φ` is standard normal pdf.
  - MC: same sampling as monte_carlo_var, compute mean of tail.
  - Returns `CVaRResult(method, confidence, horizon_days, value_brl, per_leg, n_observations, seed)`.
  - Invariant: CVaR ≥ VaR for same confidence → test for this.

### 4. Stress testing (`backend/app/risk/stress.py`)

- `HISTORICAL_SCENARIOS: tuple[HistoricalScenario, ...]` — 4 built-ins matching `.claude/skills/risk-engine-patterns/references/stress_scenarios.md`:
  - 2008 GFC: CBOT soja -35%, milho -42%, FX +40%
  - 2012 US Drought: CBOT soja +35%, milho +45%, FX +8%
  - 2020 COVID: CBOT soja -12%, milho -18%, FX +35%
  - 2022 Ukraine War: CBOT soja +25%, milho +30%, FX -5%
- `@dataclass(frozen=True) class HistoricalScenario`: `name: str`, `cbot_soja: Decimal`, `cbot_milho: Decimal`, `basis_soja: Decimal`, `basis_milho: Decimal`, `fx: Decimal`, `source_period: str`.
  - For historical 4 scenarios: basis shocks are 0 (keep them on the DB template for user-customization).
- `@dataclass(frozen=True) class StressResult`: `scenario_name: str`, `total_pnl_brl: Decimal`, `per_commodity_pnl: dict[Commodity, Decimal]`, `per_leg_pnl: dict[Literal["cbot","basis","fx"], Decimal]`.
- `def apply_scenario(exposure: AggregateExposure, prices_current: dict, scenario: HistoricalScenario) -> StressResult`:
  - For each commodity:
    - Shocked CBOT = current × (1 + shock_cbot).
    - Shocked FX = current × (1 + shock_fx).
    - P&L = exposure × (shocked_price - current_price) × commodity-specific conversion.
  - Use `pricing.mtm_value_brl` consistently; do not inline math.
- `def run_all_historical(exposure, prices_current) -> list[StressResult]` — returns list of 4.

### 5. API endpoints (`backend/app/api/v1/risk.py`)

- `router = APIRouter(prefix="/risk", tags=["risk"])`.
- `POST /risk/var`:
  - Body: `{method: "historical"|"parametric"|"monte_carlo", confidence: Decimal, horizon_days: int, window: int = 252}`.
  - Loads current user's open positions via the 4 instrument tables + fixations.
  - Computes `AggregateExposure` via `app.risk.exposure.aggregate_exposure`.
  - Loads price history from `prices` table (last `window + buffer` observations per instrument).
  - Computes weights from exposure (tons × delta per leg).
  - Calls the corresponding `var.py` function.
  - Returns `VaRResult` serialized.
- `POST /risk/cvar`: same pattern, returns `CVaRResult`.
- `POST /risk/stress/historical`:
  - Returns `list[StressResult]` for the 4 built-in scenarios applied to user's current portfolio.
- `POST /risk/stress/custom`:
  - Body: `scenario_id: UUID | HistoricalScenario payload`.
  - If id provided, load from `scenarios` table (must be owned by user).
  - Returns `StressResult`.
- `POST /risk/recalculate` (stub — called by Airflow's `trigger_mtm_recalc`):
  - Returns `{"status": "ok", "recalculated_at": now()}` for now; Phase 11+ will populate a caching layer.

Every endpoint: `Depends(get_current_user)`, `response_model=...`, structured logging with `method`, `confidence`, `horizon_days` keys.

Wire into `app.main.py`: `app.include_router(risk.router, prefix="/api/v1")`.

### 6. Unit tests

`backend/tests/unit/risk/test_var.py`:

- Synthetic factor returns: 1000 days of `N(0, 0.01)` IID across 3 factors.
- Weights: equal weight 1/3 each.
- Tests:
  - `test_parametric_flat_matches_formula`: expected = `1.645 × sqrt(w' Σ w) × portfolio_value`; assert within 1%.
  - `test_historical_approximates_parametric_on_normal`: on N(0, σ) returns, historical ≈ parametric within 10% (finite sample noise).
  - `test_mc_reproducible_with_seed`: call with seed=42 twice; identical results to 6 decimals.
  - `test_per_leg_sums_geq_flat_on_positive_corr`: on correlated factors, sum of per-leg VaRs ≥ flat VaR (diversification benefit).
  - `test_sqrt_h_scaling_parametric`: VaR(h=10) ≈ VaR(h=1) × sqrt(10) within 1%.
  - `test_confidence_monotonic`: VaR at 99% > VaR at 95%.
- Property test (`hypothesis` library is optional; do simple parametrize):
  - VaR always ≥ 0 (magnitude).
  - Doubling all weights doubles VaR (linearity).

`backend/tests/unit/risk/test_cvar.py`:
- `test_cvar_geq_var_same_confidence`
- `test_cvar_parametric_closed_form`: on N(0,σ), ES ≈ φ(z)/(1-α) × σ.
- `test_cvar_reproducible`

`backend/tests/unit/risk/test_stress.py`:
- Known portfolio: 1000 ton soja buy, CBOT=1000, FX=5, basis=0.5. Apply 2008 GFC scenario (CBOT -35%, FX +40%).
  - Compute expected P&L by hand: `1000 × (price_new - price_old)` where prices use `pricing.price_brl_ton`.
  - Assert match within 1e-4.
- `test_run_all_historical_returns_4_scenarios`
- `test_custom_scenario_applied` — pass a custom scenario with only CBOT soja -10%, assert milho P&L is 0, FX P&L is 0, soja P&L is non-zero and negative for a buy position.

### 7. Dev fixtures

`backend/tests/fixtures/price_history.py`:
- Helper to generate synthetic price DataFrames deterministically (seed-based).
- Used by all risk unit tests.

## Constraints

- MC must use the seed from `settings.MC_SEED` if not explicitly passed.
- NO `np.random` calls without explicit `Generator(seed)`.
- NO `float` inputs to user-facing functions — accept `Decimal` at the API boundary, convert internally once.
- Coverage on `app.risk/` must stay ≥90% after this phase.
- Stress `apply_scenario` MUST reuse `pricing.mtm_value_brl` — no inline math.

## MANDATORY validation

1. `cd backend && uv run mypy app/risk --strict`  → 0 errors
2. `cd backend && uv run ruff check app tests`  → clean
3. `cd backend && uv run pytest tests/unit/risk/ -v --cov=app.risk --cov-report=term-missing`  → all pass, coverage ≥90%
4. `cd backend && uv run pytest tests/integration/ -v`  → unit-like integration tests pass (API tests that don't need Supabase); the full integration suite is in Phase 5's domain — if none exist yet in integration/, skip
5. `cd backend && uv run python -c "
import asyncio
from httpx import AsyncClient
from app.main import app
async def smoke():
    async with AsyncClient(app=app, base_url='http://test') as c:
        # health first (no auth)
        r = await c.get('/api/v1/health'); assert r.status_code == 200
        # risk endpoints require auth; unauthorized should be 401
        r = await c.post('/api/v1/risk/var', json={'method':'parametric','confidence':0.95,'horizon_days':1})
        assert r.status_code == 401, f'expected 401 got {r.status_code}'
        print('risk endpoints wired + auth-gated')
asyncio.run(smoke())
"`  → prints the ok message
6. `cd backend && uv run python -c "
from decimal import Decimal
from app.risk.stress import HISTORICAL_SCENARIOS
print(len(HISTORICAL_SCENARIOS), 'scenarios:', [s.name for s in HISTORICAL_SCENARIOS])
"`  → prints `4 scenarios: [...]`
7. `cd backend && uv run pytest tests/unit/risk/test_stress.py::test_gfc_scenario -v`  → passes with printed sample output

Invariants:
- [ ] mypy strict: 0 errors
- [ ] Coverage on app.risk/ ≥ 90%
- [ ] All 3 VaR methods implemented and tested
- [ ] MC reproducibility verified (same seed → same number)
- [ ] CVaR ≥ VaR tested
- [ ] 4 historical scenarios present
- [ ] Risk endpoints require authentication (401 without JWT)
- [ ] No inline pricing math outside `risk/pricing.py`

## Commit + push

```bash
git add -A
git status --short
git commit -m "feat(risk): Phase 6 — VaR (3 methods) + CVaR + stress (historical + custom)

- risk/var.py: historical, parametric, Monte Carlo VaR with flat + per-leg breakdown
- risk/cvar.py: Expected Shortfall for all 3 methods; CVaR ≥ VaR invariant test
- risk/stress.py: 4 historical scenarios (GFC, drought, COVID, Ukraine) + custom; reuses pricing.mtm_value_brl
- risk/returns.py: return series builders with alignment + rolling window
- api/v1/risk.py: POST /var, /cvar, /stress/historical, /stress/custom, /recalculate; auth-gated
- MC reproducibility via settings.MC_SEED; seed-controlled rng.default_rng
- 25+ risk unit tests; coverage on app.risk/ ≥ 90%

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin main
```

## COWORK HANDOFF

```
=== COWORK HANDOFF — PHASE 6 BEGIN ===

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
  subject: feat(risk): Phase 6 — VaR (3 methods) + CVaR + stress (historical + custom)
  push:    <paste the "To ... main -> main" line>

Validation matrix:
  [✓/✗] 1. mypy strict app/risk        <N source files, 0 errors>
  [✓/✗] 2. ruff                         <clean>
  [✓/✗] 3. pytest + coverage            <N/N passed, coverage=XX%>
  [✓/✗] 4. integration tests            <N/N passed | N/A>
  [✓/✗] 5. risk endpoints auth smoke    <ok | error>
  [✓/✗] 6. historical scenarios count   <4: [names]>
  [✓/✗] 7. GFC stress test              <passed | failed>

Sample results (paste verbatim from test runs):
  parametric_var (95%, 1d, synthetic portfolio):  <value_brl>
  historical_var (95%, 1d, same portfolio):        <value_brl>
  monte_carlo_var (95%, 1d, seed=42, N=10k):      <value_brl>
  CVaR vs VaR (97.5%, 1d):                         CVaR=<value>, VaR=<value>, ratio=<ratio>
  2008 GFC P&L on 1000t soja buy:                  <value_brl>

Files created:
  backend/app/risk/:          returns.py, var.py, cvar.py, stress.py
  backend/app/api/v1/:        risk.py
  backend/tests/unit/risk/:   test_var.py, test_cvar.py, test_stress.py, + fixtures

Blockers / errors (if ❌):
  <step number>: <last 20 lines of command output>
  hypothesis: <your best guess at cause>
  scope-of-fix: <within prompt scope / requires Diego>

Next expected action (Diego):
  - Open http://localhost:8000/api/v1/docs, authenticate, call POST /risk/var with a sample body; sanity-check the number.
  - Call POST /risk/stress/historical; expect 4 scenarios with signed P&L.
  - Cross-check one scenario by hand against the value on the handoff.
  - Return to Cowork for Phase 7 (MC fan chart + correlation + attribution).

Open questions for Diego:
  <list or "none">

=== COWORK HANDOFF — PHASE 6 END ===
```
