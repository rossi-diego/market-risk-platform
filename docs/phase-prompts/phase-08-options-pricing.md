# Phase 8 — Options pricing (ADVANCED, optional for MVP)

> Paste-load: read this file end-to-end, execute every section. Bypass mode is assumed active.

## Context

Phase 8 delivers option pricing + Greeks for CBOT and FX options already modelled in the DB (instruments `european_option`, `american_option`, `barrier_option`). This upgrades `risk.aggregate_exposure` to stop raising `NotImplementedError` on options.

**This phase is OPTIONAL for MVP.** If you'd rather ship the portfolio without exotic option support, skip to Phase 9 (frontend scaffold) and wire an ADR (`docs/adr/0004-options-deferred.md`) stating V2 deferral. If you keep Phase 8, budget 4-6 hours — MC for barriers is the heavy part.

Reference:
- `CLAUDE.md` — Risk Metrics (Phase 8 `options/` subtree).
- `.claude/skills/risk-engine-patterns/SKILL.md`.
- Hull (2022) Ch. 13 (BSM), Ch. 21 (American binomial), Ch. 24 (Exotics).

## Running mode

`--dangerously-skip-permissions` active. Commit + push to main on validation success.

## Tasks

### 1. Black-Scholes-Merton (European options)

`backend/app/risk/options/bsm.py`:

- `@dataclass class BSMResult`: `price: Decimal`, `delta`, `gamma`, `vega`, `theta`, `rho` (all `Decimal`).
- `def bsm_price(S, K, T, r, sigma, option_type: Literal["call","put"], q: Decimal = Decimal("0")) -> BSMResult`:
  - `S` = spot, `K` = strike, `T` = years to maturity, `r` = risk-free rate, `sigma` = volatility (annualized), `q` = dividend/convenience yield.
  - Uses `scipy.stats.norm` CDF and PDF. Accepts/returns `Decimal`; converts to `float` internally.
  - All 5 Greeks from closed-form.
- `def implied_vol(S, K, T, r, market_price, option_type, q=0) -> Decimal`:
  - Newton-Raphson with a Brent fallback. Raise `ValueError` if no solution in `[0.001, 5.0]`.

### 2. Binomial CRR (American options)

`backend/app/risk/options/binomial.py`:

- `def crr_american(S, K, T, r, sigma, option_type, q=0, n_steps: int = 500) -> BSMResult`:
  - Cox-Ross-Rubinstein tree.
  - Greeks via finite differences on the tree output (central diff for delta/gamma, forward for theta).
  - Convergence: `n_steps=1000` matches BSM for European options within `1e-4` on price.

### 3. Barrier options (Monte Carlo)

`backend/app/risk/options/barrier.py`:

- `def barrier_mc(S, K, T, r, sigma, option_type, barrier_type, barrier_level, rebate: Decimal, q=0, n_paths: int = 50_000, n_steps: int = 252, seed: int | None = None) -> BSMResult`:
  - Path simulation with GBM, checks barrier hit per step.
  - `up_and_in`, `up_and_out`, `down_and_in`, `down_and_out` via monitoring logic.
  - Greeks via bump-and-revalue (finite differences on `S`, `sigma`, `T`).
  - Uses `np.random.default_rng(seed or settings.MC_SEED)` for reproducibility.
- Analytic check: `up_and_out` with barrier = `S × 10` should ≈ vanilla BSM call (up-and-out with very high barrier = never hit = vanilla).

### 4. Unified Greeks + delta for aggregate_exposure

`backend/app/risk/options/greeks.py`:

- `def option_delta_brl_ton(option_instrument, spot, ...) -> Decimal` — dispatch to BSM/binomial/barrier based on instrument type, return delta converted to BRL/ton sensitivity.
- Update `app/risk/exposure.py:aggregate_exposure` to call `option_delta_brl_ton` for `european_option`, `american_option`, `barrier_option` instead of raising NotImplementedError.

### 5. Tests

`backend/tests/unit/risk/options/`:

- `test_bsm.py` (8+ tests):
  - Put-call parity: `call_price + K*exp(-r*T) == put_price + S*exp(-q*T)` within `1e-6`.
  - At-the-money delta ≈ 0.5 (call) / -0.5 (put) for `T=1, r=0`.
  - Implied vol roundtrip: price → IV → price matches within `1e-4`.
- `test_binomial.py` (4+ tests):
  - European binomial (same formula) → matches BSM at `n=1000`.
  - American put > European put on dividend-paying stocks.
- `test_barrier.py` (4+ tests):
  - Up-and-out with barrier → ∞ ≈ vanilla call.
  - In-out parity: `up_and_in + up_and_out == vanilla` within MC noise (N=100k).
  - MC reproducibility with explicit seed.
- Coverage on `app.risk.options/` must be ≥85% (barrier MC Greeks via bump have natural floor).

## Constraints

- NO new deps (scipy, numpy already present).
- All Greeks must be `Decimal` at the API boundary.
- Barrier MC: seed must be honored; test asserts bit-exact across runs.

## MANDATORY validation

1. `cd backend && uv run mypy app/risk --strict`  → 0 errors
2. `cd backend && uv run ruff check .`  → clean
3. `cd backend && uv run pytest tests/unit/risk/ -v --cov=app.risk --cov-report=term-missing`  → all pass, coverage on `app.risk/` ≥ 90% (options subtree ≥ 85%)
4. `cd backend && uv run python -c "
from decimal import Decimal
from app.risk.options.bsm import bsm_price
r = bsm_price(Decimal('100'), Decimal('100'), Decimal('1'), Decimal('0.05'), Decimal('0.2'), 'call')
print('ATM call price:', r.price, 'delta:', r.delta)
"`  → price ≈ 10.45, delta ≈ 0.6368
5. Put-call parity passes in tests.

Invariants:
- [ ] BSM price matches textbook values within `1e-4`
- [ ] Binomial converges to BSM at `n=1000`
- [ ] Barrier up-and-out with huge barrier ≈ vanilla
- [ ] In-out parity within MC noise
- [ ] aggregate_exposure no longer raises NotImplementedError for options

## Commit + push

```bash
git add -A
git commit -m "feat(risk): Phase 8 — options pricing (BSM + binomial + barrier MC)

- risk/options/bsm.py: closed-form Black-Scholes-Merton + 5 Greeks + implied vol
- risk/options/binomial.py: Cox-Ross-Rubinstein American option pricer
- risk/options/barrier.py: Monte Carlo barrier pricer (4 barrier types, bump-Greeks)
- risk/options/greeks.py: unified option_delta_brl_ton dispatcher
- exposure.py: aggregate_exposure now handles options via option_delta_brl_ton
- 16+ new tests; coverage on app.risk/ stays ≥90%

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin main
```

## COWORK HANDOFF

Standard format; include BSM/binomial/barrier sample prices, parity residuals, and MC seed verification.
