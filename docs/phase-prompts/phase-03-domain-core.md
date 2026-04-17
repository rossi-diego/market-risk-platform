# Phase 3 — Domain core: pricing + exposure + types

> Paste-load: read this file end-to-end, execute every section. Bypass mode is assumed active.

## Context

Phase 3 implements the pure-function heart of the risk engine: price formation (BRL/ton formula, unit conversions, per-leg deltas) and per-leg open exposure aggregation for physical frames. Every conversion math in the codebase MUST live in `risk/pricing.py` only. No inline math elsewhere, now or later.

Reference:
- `CLAUDE.md` — Price Formation Model, Exposure Decomposition, Fixation Modes.
- `.claude/skills/commodity-price-decomposition/SKILL.md` (MUST read — contains worked examples and anti-patterns).
- `.claude/skills/risk-engine-patterns/SKILL.md` (type rigor, reproducibility).
- `docs/adr/0003-risk-aggregation.md`.

## Running mode

`--dangerously-skip-permissions` active. Commit + push to main on validation success.

## Tasks

### 1. Risk module scaffolding

- `backend/app/risk/__init__.py` — empty.
- `backend/app/risk/types.py`:
  - `@dataclass(frozen=True, slots=True) class LegExposure`:
    - `cbot_qty_tons: Decimal`  — open tons on CBOT leg
    - `basis_qty_tons: Decimal`  — open tons on basis leg
    - `fx_qty_tons: Decimal`  — open tons on FX leg
    - All must be ≥ 0 (validate in `__post_init__`, raise `ValueError` on negative).
  - `@dataclass(frozen=True, slots=True) class FrameExposure`:
    - `frame_id: UUID`, `commodity: Commodity`, `side: Side`, `total_tons: Decimal`, `open: LegExposure`, `locked: LegExposure`.
  - `@dataclass(frozen=True, slots=True) class AggregateExposure`:
    - `by_commodity: dict[Commodity, LegExposure]` — net per leg per commodity (signed: buy positive, sell negative).
    - `total: LegExposure` — sum across commodities (absolute magnitudes not useful here; keep signed).
  - Custom exception `DomainError(Exception)` for invariant violations.

### 2. Pricing functions (`backend/app/risk/pricing.py`)

All functions accept and return `Decimal`. No `float` anywhere in financial math.

Constants:

```python
from decimal import Decimal
from app.models.enums import Commodity

TONS_TO_BUSHELS: dict[Commodity, Decimal] = {
    Commodity.SOJA: Decimal("36.744"),
    Commodity.MILHO: Decimal("56.0"),
}
```

Functions (all must have type hints, docstrings, and tests):

- `price_brl_ton(commodity: Commodity, cbot_uscbu: Decimal, fx_brl_usd: Decimal, premium_usd_bu: Decimal) -> Decimal`
  - Formula: `(cbot / 100 / bushels_per_ton) * fx + premium * fx / bushels_per_ton`
- `mtm_value_brl(commodity: Commodity, quantity_tons: Decimal, cbot_uscbu: Decimal, fx_brl_usd: Decimal, premium_usd_bu: Decimal) -> Decimal`
  - Returns total BRL value: `price_brl_ton(...) * quantity_tons`.
- `cbot_delta_brl_ton(commodity: Commodity, fx_brl_usd: Decimal) -> Decimal`
  - Sensitivity of BRL/ton to a 1 USc/bu CBOT move. = `fx_brl_usd / 100 / bushels_per_ton`.
- `fx_delta_brl_ton(commodity: Commodity, cbot_uscbu: Decimal, premium_usd_bu: Decimal) -> Decimal`
  - Sensitivity of BRL/ton to a 0.01 BRL/USD FX move. = `(cbot / 100 / bushels + premium / bushels) * Decimal("0.01")`.
- `basis_delta_brl_ton(commodity: Commodity, fx_brl_usd: Decimal) -> Decimal`
  - Sensitivity to a 1 USD/bu basis move. = `fx_brl_usd / bushels_per_ton`.

Naming: use `basis` throughout (not `premium`) to match the DB/ADR terminology.

### 3. Exposure aggregation (`backend/app/risk/exposure.py`)

- `def open_exposure_frame(frame: PhysicalFrame, fixations: list[PhysicalFixation]) -> FrameExposure`
  - Compute `locked_cbot`, `locked_basis`, `locked_fx` as sums of `fixation.quantity_tons` over fixations whose `fixation_mode` locks that leg:
    - CBOT locked by: `FLAT`, `CBOT`, `CBOT_BASIS`.
    - Basis locked by: `FLAT`, `CBOT_BASIS`, `BASIS`.
    - FX locked by: `FLAT`, `FX`.
  - Open per leg = `frame.quantity_tons - locked`.
  - If any `locked > frame.quantity_tons` → raise `DomainError` with message `"Over-locked leg {leg}: {locked} > {total}"`.
  - Return `FrameExposure(frame_id, commodity, side, total_tons, open=LegExposure(...), locked=LegExposure(...))`.

- `def aggregate_exposure(frames_with_fixations, cbot_derivs, basis_fwds, fx_derivs) -> AggregateExposure`
  - Signature:
    ```python
    def aggregate_exposure(
        frames_with_fixations: list[tuple[PhysicalFrame, list[PhysicalFixation]]],
        cbot_derivs: list[CBOTDerivative],
        basis_fwds: list[BasisForward],
        fx_derivs: list[FXDerivative],
    ) -> AggregateExposure:
    ```
  - For each frame: compute `FrameExposure`, apply side sign (buy=+1, sell=-1), add to per-commodity leg totals.
  - For each CBOT derivative: add signed `quantity_contracts * 5000 / bushels_per_ton` to the CBOT leg of its commodity. (5000 bu = CBOT contract size for ZS and ZC.)
  - Skip derivatives whose `instrument` is `european_option | american_option | barrier_option` — raise `NotImplementedError("Option delta requires Phase 8 pricing engine")`. This is intentional: Phase 3 is linear-only.
  - For each basis forward: add signed `quantity_tons` to the basis leg of its commodity.
  - For each FX derivative: `notional_usd / fx_at_some_reference_rate` converted to an equivalent tons-like unit of FX delta. Simpler: add signed `notional_usd` to a `fx_notional_usd` bucket that is reported separately (don't force a ton unit on FX). → Extend `AggregateExposure` with `fx_notional_usd: Decimal` and adjust docstring.
  - Skip FX options (same `NotImplementedError`).

### 4. Unit tests

`backend/tests/unit/risk/test_pricing.py`:

Parametrized:
- `price_brl_ton(SOJA, 1000, 5, 0.5)`:
  - Expected = `(1000/100/36.744)*5 + 0.5*5/36.744 = 1.3606 + 0.0680 = 1.4287` (verify to 4 decimals).
- `price_brl_ton(MILHO, 400, 5, 0.3)`:
  - Expected = `(400/100/56)*5 + 0.3*5/56 = 0.3571 + 0.0268 = 0.3839`.
- `cbot_delta_brl_ton(SOJA, 5)` = `5/100/36.744 ≈ 0.013608`.
- `fx_delta_brl_ton(SOJA, 1000, 0.5)` = `(1000/100/36.744 + 0.5/36.744) * 0.01 ≈ 0.002760`.
- `basis_delta_brl_ton(SOJA, 5)` = `5/36.744 ≈ 0.136076`.
- Symmetry check: a CBOT move of 10 USc/bu multiplied by `cbot_delta_brl_ton` should equal `price_brl_ton(cbot+10) - price_brl_ton(cbot)` to 6 decimals.
- `TONS_TO_BUSHELS` has exactly the 2 commodities.

`backend/tests/unit/risk/test_exposure.py`:

- Frame 1000 tons buy, 0 fixations → open=(1000, 1000, 1000), locked=(0,0,0).
- Frame 1000 tons buy, 1 fixation mode=FLAT 300 tons → open=(700, 700, 700), locked=(300,300,300).
- Frame 1000 tons buy, 1 fixation mode=CBOT 300 + 1 mode=FX 500 → open=(700, 1000, 500), locked=(300,0,500).
- Frame 1000 tons buy, 1 fixation mode=CBOT_BASIS 400 → open=(600, 600, 1000), locked=(400,400,0).
- Frame 1000 tons buy, 1 fixation mode=BASIS 400 → open=(1000, 600, 1000), locked=(0,400,0).
- Over-lock (sum on a leg > total) → raises `DomainError` with leg name + values.
- `aggregate_exposure` with a mix of physical + CBOT future + basis forward + FX NDF → validate per-commodity + fx_notional_usd totals against hand-calculated reference.
- `aggregate_exposure` with any CBOT option → raises `NotImplementedError`.

Test config:
- pytest-cov must enforce `--cov=app.risk --cov-report=term-missing` with a threshold ≥95% via `[tool.coverage.report] fail_under = 95` added to `backend/pyproject.toml`.

## Constraints

- NO inline conversion math outside `risk/pricing.py`.
- NO `float` in any pricing or exposure function — Decimal throughout.
- NO implementation of option deltas here (raises `NotImplementedError`).
- Coverage floor on `app.risk/` module is 95% — if less, validation fails.

## MANDATORY validation

1. `cd backend && uv run mypy app/risk --strict`  → 0 errors
2. `cd backend && uv run ruff check app/risk tests/unit/risk`  → clean
3. `cd backend && uv run pytest tests/unit/risk/ -v --cov=app.risk --cov-report=term-missing`  → all pass, coverage ≥95%
4. `cd backend && uv run python -c "from decimal import Decimal; from app.models.enums import Commodity; from app.risk.pricing import price_brl_ton; print(price_brl_ton(Commodity.SOJA, Decimal('1000'), Decimal('5'), Decimal('0.5')))"`  → prints something close to `1.4287...`
5. `cd backend && uv run python -c "from app.risk.exposure import open_exposure_frame; print('ok')"`  → prints "ok"

Invariants:
- [ ] mypy strict on risk/: 0 errors
- [ ] risk/ coverage ≥95%
- [ ] Pricing sanity check: sample `price_brl_ton` matches hand calculation (tolerance 1e-4)
- [ ] Exposure tests cover all 5 fixation modes on a single frame
- [ ] Over-lock raises DomainError
- [ ] CBOT option in aggregate_exposure raises NotImplementedError
- [ ] No `float` literals or conversions introduced into risk/

## Commit + push

```bash
git add -A
git status --short
git commit -m "feat(risk): Phase 3 — pricing + per-leg exposure aggregation

- risk/pricing.py: BRL/ton formula + 3 unit-correct sensitivity deltas (CBOT, FX, basis), all Decimal
- risk/exposure.py: open_exposure_frame respecting 5 fixation modes; aggregate_exposure with option guards (NotImplementedError raised until Phase 8)
- risk/types.py: LegExposure, FrameExposure, AggregateExposure with invariant checks
- Coverage floor 95% on app.risk/; 25+ pricing + exposure unit tests
- Commodity TONS_TO_BUSHELS: soja=36.744, milho=56.0

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin main
```

## COWORK HANDOFF

```
=== COWORK HANDOFF — PHASE 3 BEGIN ===

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
  subject: feat(risk): Phase 3 — pricing + per-leg exposure aggregation
  push:    <paste the "To ... main -> main" line>

Validation matrix:
  [✓/✗] 1. mypy strict app/risk    <N source files, 0 errors | N errors>
  [✓/✗] 2. ruff clean              <clean | N issues>
  [✓/✗] 3. pytest + coverage       <N/N passed, coverage=XX%>
  [✓/✗] 4. pricing sanity          <computed value vs 1.4287±1e-4>
  [✓/✗] 5. exposure import smoke   <ok | error>

Files created:
  backend/app/risk/:   types.py, pricing.py, exposure.py, __init__.py
  backend/tests/unit/risk/:  test_pricing.py (N tests), test_exposure.py (N tests)

Key numbers from tests (paste verbatim):
  price_brl_ton(SOJA, 1000, 5, 0.5)   = <value>
  price_brl_ton(MILHO, 400, 5, 0.3)   = <value>
  cbot_delta_brl_ton(SOJA, 5)         = <value>
  Coverage on app.risk/               = <XX%>

Blockers / errors (if ❌):
  <step number>: <last 20 lines of command output>
  hypothesis: <your best guess at cause>
  scope-of-fix: <within prompt scope / requires Diego>

Next expected action (Diego):
  - Spot-check the sanity numbers above against a calculator.
  - Return to Cowork to validate Phase 3 and trigger Phase 4 (price ingestion).

Open questions for Diego:
  <list or "none">

=== COWORK HANDOFF — PHASE 3 END ===
```
