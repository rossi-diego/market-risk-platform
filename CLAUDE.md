# CLAUDE.md — market-risk-platform

Project-level instructions for AI-assisted development. Read this before making any code change.

---

## Project Purpose

Production-grade web application for market risk analysis of **long and short** positions in soybean (soja) and corn (milho) in the Brazilian agribusiness context. Supports physical contracts (with partial fixações), CBOT derivatives, basis forwards, and FX derivatives as first-class instruments. Covers the full risk management lifecycle: position entry → mark-to-market → VaR/CVaR (flat + per-leg) → stress testing → attribution. Multi-user with Supabase Auth + RLS. Serves as a portfolio demonstration of end-to-end data engineering + quantitative finance skills.

Design decisions are captured in [`docs/adr/`](docs/adr/0000-index.md). Any change to domain model, risk methodology, or major architectural layering should reference or extend an ADR.

---

## Price Formation Model

This is the core domain model. Every calculation derives from it.

### Soybean (Soja)

```
Price [BRL/ton] = (CBOT [USc/bu] / 100 / 36.744) × FX [BRL/USD] + Premium [USD/bu] × FX [BRL/USD] / 36.744
```

- **CBOT**: `ZS=F` via yfinance (CBOT front-month, USc/bushel)
- **FX**: `USDBRL=X` via yfinance (BRL per 1 USD)
- **Premium**: user-supplied per operation AND a separate MTM premium configured globally
- **Conversion factor**: 1 ton = 36.744 bushels

### Corn (Milho)

```
Price [BRL/ton] = (CBOT_PROXY [USc/bu] / 100 / 56.0) × FX [BRL/USD] + Premium [USD/bu] × FX [BRL/USD] / 56.0
```

- **CBOT**: `ZC=F` via yfinance — **proxy only**, flagged as `price_source: "CBOT_PROXY_YFINANCE"`. In production this would be replaced by B3 `CCM` contracts via Economatica/Refinitiv.
- **FX**: same `USDBRL=X` feed
- **Premium**: same user-supplied model as soja
- **Conversion factor**: 1 ton = 56.0 bushels (metric)

### Price Source Flags

Every price record in the DB must carry a `price_source` enum:

```python
class PriceSource(str, Enum):
    YFINANCE_CBOT    = "YFINANCE_CBOT"       # ZS=F, ZC=F
    YFINANCE_FX      = "YFINANCE_FX"         # USDBRL=X
    B3_OFFICIAL      = "B3_OFFICIAL"         # future, not implemented
    USER_MANUAL      = "USER_MANUAL"         # imported or typed
    CBOT_PROXY       = "CBOT_PROXY_YFINANCE" # ZC=F standing in for B3
```

### Exposure Decomposition

MTM P&L is decomposed into three independent **legs**. Terminology: "basis" is the industry-standard name; "prêmio" in Portuguese and "premium" in informal English refer to the same leg. The DB and code use `basis` throughout.

| Leg        | Exposure                           | Unit        |
|------------|------------------------------------|-------------|
| CBOT Delta | ΔP&L per 1 USc/bu CBOT move        | BRL/ton     |
| FX Delta   | ΔP&L per 0.01 BRL/USD FX move      | BRL/ton     |
| Basis Delta| ΔP&L per 1 USD/bu basis/prêmio move| BRL/ton     |

This decomposition is shown per-position, per-frame, and aggregated at the portfolio level.

**Where each instrument contributes:**

| Instrument family      | CBOT leg | Basis leg | FX leg |
|------------------------|:--------:|:---------:|:------:|
| Physical (open legs)   | ✓        | ✓         | ✓      |
| CBOT derivatives       | ✓        | —         | —      |
| Basis forwards         | —        | ✓         | —      |
| FX derivatives         | —        | —         | ✓      |

Physical frames contribute to a leg only when that leg is still *open* (not yet fixed via a fixação — see next section). Derivatives always contribute on their single leg. Risk aggregation per leg and flat is formalized in [ADR-0003](docs/adr/0003-risk-aggregation.md).

---

## Instrument Schema

Positions are modeled as **four first-class tables**, one per instrument family. Shared conventions (`user_id`, `side`, `status`, `counterparty`, `notes`, timestamps) live on all of them; family-specific columns and CHECK constraints enforce everything else at the DB level. Rationale and alternatives in [ADR-0001](docs/adr/0001-instrument-model.md).

### Common fields (every instrument table)

- `id: UUID` (primary key)
- `user_id: UUID` (FK to `auth.users`, RLS predicate)
- `side: Literal["buy", "sell"]` — long (`buy`) or short (`sell`)
- `status: Literal["open", "partial", "closed", "expired"]`
- `counterparty: str | None`
- `notes: str | None`
- `created_at`, `updated_at: timestamptz`

### 1. Physical contracts — `physical_frames` + `physical_fixations`

Physical is modeled as a **Frame (parent) + Fixações (children)** hierarchy. A frame is the contract for total tonnage and delivery window; fixações are partial pricing events that lock one or more legs on a subset of the tonnage. See [ADR-0002](docs/adr/0002-fixacao-model.md).

```python
class PhysicalFrame(BaseModel):
    id: UUID
    user_id: UUID
    commodity: Literal["soja", "milho"]
    side: Literal["buy", "sell"]
    quantity_tons: Decimal           # total tonnage of the frame
    delivery_start: date
    delivery_end: date
    counterparty: str | None
    status: Literal["open", "partial", "closed", "expired"]
    notes: str | None

class PhysicalFixation(BaseModel):
    id: UUID
    frame_id: UUID                   # FK → physical_frames.id
    fixation_mode: Literal["flat", "cbot", "cbot_basis", "basis", "fx"]
    quantity_tons: Decimal           # how many tons this fixation locks
    fixation_date: date
    cbot_fixed: Decimal | None       # USc/bu — required for flat, cbot, cbot_basis
    basis_fixed: Decimal | None      # USD/bu — required for flat, cbot_basis, basis
    fx_fixed: Decimal | None         # BRL/USD — required for flat, fx
    reference_cbot_contract: str | None  # e.g. "ZSK26"
    notes: str | None
```

### 2. CBOT derivatives — `cbot_derivatives`

```python
class CBOTDerivative(BaseModel):
    id: UUID
    user_id: UUID
    commodity: Literal["soja", "milho"]
    instrument: Literal["future", "swap", "european_option", "american_option", "barrier_option"]
    side: Literal["buy", "sell"]
    contract: str                    # e.g. "ZSK26", "ZCN26"
    quantity_contracts: Decimal
    trade_date: date
    trade_price: Decimal             # USc/bu
    maturity_date: date
    # option-specific (NULL if instrument is future or swap)
    option_type: Literal["call", "put"] | None
    strike: Decimal | None
    # barrier-specific (NULL unless instrument = "barrier_option")
    barrier_type: Literal["up_and_in", "up_and_out", "down_and_in", "down_and_out"] | None
    barrier_level: Decimal | None
    rebate: Decimal | None
    status: Literal["open", "partial", "closed", "expired"]
    counterparty: str | None
    notes: str | None
```

### 3. Basis forwards — `basis_forwards`

```python
class BasisForward(BaseModel):
    id: UUID
    user_id: UUID
    commodity: Literal["soja", "milho"]
    side: Literal["buy", "sell"]
    quantity_tons: Decimal
    trade_date: date
    basis_price: Decimal             # USD/bu
    delivery_date: date
    reference_cbot_contract: str     # e.g. "ZSK26"
    status: Literal["open", "partial", "closed", "expired"]
    counterparty: str | None
    notes: str | None
```

### 4. FX derivatives — `fx_derivatives`

```python
class FXDerivative(BaseModel):
    id: UUID
    user_id: UUID
    instrument: Literal["ndf", "swap", "european_option", "american_option", "barrier_option"]
    side: Literal["buy", "sell"]
    notional_usd: Decimal
    trade_date: date
    trade_rate: Decimal              # BRL/USD at trade
    maturity_date: date
    option_type: Literal["call", "put"] | None
    strike: Decimal | None
    barrier_type: Literal["up_and_in", "up_and_out", "down_and_in", "down_and_out"] | None
    barrier_level: Decimal | None
    rebate: Decimal | None
    status: Literal["open", "partial", "closed", "expired"]
    counterparty: str | None
    notes: str | None
```

### Audit trail — `trade_events`

Polymorphic log of lifecycle events across all four families (`open | fill | partial_close | close | expire | adjust`), keyed by `(instrument_table, instrument_id)`. No hard FK; application code is the sole writer.

### Global config — `mtm_premiums`

MTM basis (used for marking open legs to market, distinct from the basis locked at trade time) is a **global config per commodity**, editable by the user in the dashboard settings. Lives in the `mtm_premiums` table.

---

## Fixation Modes

The five fixation modes and which legs each one locks:

| Mode           | CBOT leg | Basis leg | FX leg | Typical usage                              |
|----------------|:--------:|:---------:|:------:|---------------------------------------------|
| `flat`         | locked   | locked    | locked | All three legs locked simultaneously        |
| `cbot`         | locked   | —         | —      | "Fixação de bolsa" / to-arrive contract     |
| `cbot_basis`   | locked   | locked    | —      | "Fixou bolsa + prêmio", FX still open       |
| `basis`        | —        | locked    | —      | "Fixação de prêmio/basis" standalone        |
| `fx`           | —        | —         | locked | "Fixação de dólar" standalone               |

The DB enforces a CHECK constraint ensuring that `cbot_fixed`, `basis_fixed`, `fx_fixed` are non-null exactly for the legs that the `fixation_mode` locks. Application layer enforces that cumulative locked tonnage per leg never exceeds the frame's `quantity_tons` (returns 409 Conflict on violation).

Open exposure on a frame, per leg:

```
open_tons(leg) = frame.quantity_tons − Σ fixation.quantity_tons
                                       for fixation in frame.fixations
                                       where fixation.fixation_mode locks this leg
```

Canonical implementation: `backend/app/risk/exposure.py:open_exposure_frame()`.

---

## Data Sources & Update Schedule

| Feed          | Ticker       | Source   | Schedule (BRT)        | Fallback       |
|---------------|--------------|----------|-----------------------|----------------|
| Soja CBOT     | `ZS=F`       | yfinance | 18:00 weekdays        | Last valid     |
| Milho CBOT    | `ZC=F`       | yfinance | 18:00 weekdays        | Last valid     |
| FX USD/BRL    | `USDBRL=X`   | yfinance | 18:00 weekdays        | Last valid     |
| Milho B3      | `CCM` (B3)   | —        | Not implemented       | ZC=F proxy     |

Price update is triggered by **GitHub Actions Cron** (zero-infra):

```yaml
# .github/workflows/price_update.yml
on:
  schedule:
    - cron: '0 21 * * 1-5'  # 18h BRT = 21h UTC
```

The cron job calls `POST /api/v1/prices/fetch` on the backend, which runs the yfinance fetch + upsert to Supabase.

Airflow DAG (`commodity_price_pipeline`) exists in `infra/airflow/dags/` as the production-grade equivalent. In the demo deployment, it is documented but not actively scheduled — GitHub Actions handles this.

---

## Risk Metrics — Methodology Reference

### VaR

Every method is computed in two views: **flat** (total portfolio P&L) and **per-leg** (CBOT, basis, FX independently). See [ADR-0003](docs/adr/0003-risk-aggregation.md) for methodology.

| Method      | Implementation                                    | Reference              |
|-------------|---------------------------------------------------|------------------------|
| Historical  | Order returns, percentile at α                    | Jorion (2006) Ch. 5    |
| Parametric  | z_α × σ_P × √h, with σ_P from factor covariance    | Hull (2022) Ch. 22     |
| Monte Carlo | Cholesky-correlated GBM on 3 factors, N=10,000    | Jorion (2006) Ch. 12   |

Confidence levels: 95%, 97.5% (FRTB-aligned), 99%. Horizons: 1-day and 10-day (√h scaling for parametric; path-consistent for historical and MC).

**Attribution (component VaR)** — decomposes flat VaR into position-level contributions: `c_i = ρ_{i,p} × σ_i × w_i × VaR_p / σ_p`. Sum of components equals flat VaR within rounding. Implemented in `backend/app/risk/attribution.py`.

### CVaR / Expected Shortfall

ES_α = E[L | L > VaR_α]

Computed on the same return distribution as Historical VaR. Regulatory context: Basel III/IV (FRTB) replaces VaR with ES at 97.5% as the primary capital metric.

### Stress Testing

**Historical scenarios (hard-coded):**

| Scenario         | Soja shock | Milho shock | FX shock | Source period  |
|------------------|------------|-------------|----------|----------------|
| 2008 GFC         | −35%       | −42%        | +40%     | Sep–Dec 2008   |
| 2012 US Drought  | +35%       | +45%        | +8%      | Jun–Aug 2012   |
| 2020 COVID       | −12%       | −18%        | +35%     | Mar 2020       |
| 2022 Ukraine War | +25%       | +30%        | −5%      | Feb–May 2022   |

**Hypothetical scenarios:** user-configurable via dashboard (sliders for % shock per component).

**Literature:** Jorion (2006) Ch. 14; BCBS (2009) *Principles for Sound Stress Testing*; CME SPAN methodology.

---

## Stack

### Backend

```
FastAPI 0.115+ (async)
Python 3.12+
Supabase (PostgreSQL + Auth + Storage)
SQLAlchemy 2.0 async + Alembic (for migration tracking, even with Supabase)
Pydantic v2
structlog (structured JSON logging)
pandas + openpyxl (Excel/CSV ingestion)
numpy + scipy (risk calculations)
yfinance (price feeds)
uv (dependency management)
```

### Frontend

```
Next.js 14+ App Router
TypeScript
Tailwind CSS + shadcn/ui
TanStack Query (server state)
Zustand (UI state)
Recharts (charts: time series, VaR fan, waterfall, heatmap)
```

### Infrastructure

```
Docker Compose (local dev: API + Airflow)
GitHub Actions (CI/CD + price update cron)
Vercel (frontend deploy)
Render free tier (backend deploy — cold starts accepted for demo)
Supabase (DB + Auth + Storage — hosted)
uv inside Docker for fast builds
```

> **Note on Render cold starts:** Render free tier spins down after 15 min of inactivity (~30s cold start). This is acceptable for a portfolio demo. If deploying for real users, migrate to Fly.io free tier (3 shared VMs, no sleep) or Railway ($5 credit/month, no sleep).

### Airflow (local + optional Astronomer)

```
apache-airflow 2.9+
DAG: commodity_price_pipeline
Tasks: fetch_soy → fetch_corn → fetch_fx → validate → upsert_supabase → trigger_mtm_recalc
```

---

## Repo Structure

```
market-risk-platform/
├── backend/
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── physical.py        # CRUD physical frames + fixations
│   │   │   ├── cbot.py            # CRUD CBOT derivatives
│   │   │   ├── basis.py           # CRUD basis forwards
│   │   │   ├── fx.py              # CRUD FX derivatives
│   │   │   ├── prices.py          # price history + fetch trigger
│   │   │   ├── risk.py            # VaR/CVaR/stress/attribution endpoints
│   │   │   ├── scenarios.py       # stress test config
│   │   │   ├── imports.py         # Excel/CSV upload (4 sheets)
│   │   │   └── reports.py         # PDF export
│   │   ├── core/
│   │   │   ├── config.py          # pydantic-settings, env vars
│   │   │   ├── security.py        # Supabase JWT validation
│   │   │   ├── db.py              # async engine + session
│   │   │   └── logging.py         # structlog setup
│   │   ├── models/                # SQLAlchemy 2.0 ORM (one file per family)
│   │   │   ├── base.py            # Base + mixins
│   │   │   ├── prices.py
│   │   │   ├── physical.py        # PhysicalFrame + PhysicalFixation
│   │   │   ├── cbot.py
│   │   │   ├── basis.py
│   │   │   ├── fx.py
│   │   │   ├── events.py          # TradeEvent (polymorphic audit log)
│   │   │   └── config.py          # MTMPremium, Scenario, ScenarioTemplate
│   │   ├── schemas/               # Pydantic v2 (In/Out/Update per family)
│   │   ├── services/              # business logic
│   │   │   ├── price_ingestion.py
│   │   │   ├── imports.py         # Excel parsing
│   │   │   └── status_recompute.py # derive frame.status from fixations
│   │   └── risk/
│   │       ├── pricing.py         # BRL/ton formula, unit conversions
│   │       ├── exposure.py        # per-leg open exposure for frames
│   │       ├── returns.py         # return series builders
│   │       ├── var.py             # Historical, Parametric, MC VaR (flat + per-leg)
│   │       ├── cvar.py            # Expected Shortfall
│   │       ├── mc.py              # Cholesky-correlated MC paths
│   │       ├── correlation.py     # correlation matrix + PSD guard
│   │       ├── attribution.py     # component VaR
│   │       ├── stress.py          # historical + hypothetical scenarios
│   │       ├── options/           # (Phase 8, optional)
│   │       │   ├── bsm.py         # Black-Scholes-Merton + Greeks
│   │       │   ├── binomial.py    # CRR for American options
│   │       │   ├── barrier.py     # MC for barrier options
│   │       │   └── greeks.py
│   │       └── types.py           # LegExposure, AggregateExposure, VaRResult, ...
│   ├── migrations/                # Alembic (baseline synced with Supabase)
│   ├── scripts/
│   │   └── fetch_prices.py        # CLI entry for GitHub Actions cron
│   └── tests/
│       ├── unit/risk/             # pure function tests (coverage ≥90%)
│       └── integration/           # API tests with test DB
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── (auth)/            # login, signup
│   │   │   ├── (dashboard)/
│   │   │   │   ├── page.tsx       # overview
│   │   │   │   ├── positions/     # 4-tab CRUD + frame detail + import
│   │   │   │   ├── risk/          # VaR/CVaR/stress/attribution/fan/heatmap
│   │   │   │   ├── scenarios/     # scenario builder
│   │   │   │   └── settings/      # MTM basis per commodity
│   │   │   └── middleware.ts      # Supabase session redirect
│   │   ├── components/            # shadcn/ui + custom widgets
│   │   └── lib/
│   │       ├── supabase/          # client, server, middleware helpers
│   │       ├── api/               # openapi-typescript generated types + fetch wrappers
│   │       └── formatters/        # BRL, USD/bu, %, tons, USc/bu
├── infra/
│   ├── docker-compose.yml         # postgres + airflow (local dev)
│   ├── airflow/dags/
│   │   └── commodity_price_pipeline.py
│   └── terraform/                 # Azure (optional, not for demo)
├── .github/workflows/
│   ├── ci.yml                     # lint + type + test + build (PR blocker)
│   └── price_update.yml           # daily price fetch cron (21:00 UTC / 18:00 BRT)
├── .claude/                       # AI tooling
│   ├── skills/                    # project-specific skills (see .claude/skills/README.md)
│   └── kb/                        # knowledge base docs
└── docs/
    ├── adr/                       # Architecture Decision Records (see 0000-index.md)
    ├── BUILD_PLAN.md              # phased delivery plan with CC prompts + checkpoints
    ├── ARCHITECTURE.md
    ├── RISK_METHODOLOGY.md        # formulas + literature
    ├── PRICE_MODEL.md             # CBOT/FX/Basis decomposition
    └── DEPLOY.md                  # Vercel + Render + Supabase runbook
```

---

## Conventions

- **All secrets** via environment variables. Never hardcode. Use `.env.local` (frontend) and `.env` (backend) with `.env.example` committed.
- **Supabase RLS**: Row Level Security enabled on all tables. Service role key only in backend.
- **Type hints** everywhere in Python. `mypy --strict` on `risk/` module.
- **Unit conversions** must live in `risk/pricing.py` only. No inline conversion math elsewhere.
- **Price source flag** must be set on every price record and every calculated result that depends on a price.
- **Monte Carlo** must use `np.random.seed(config.MC_SEED)` for reproducibility. Seed goes in env config.
- **API routes**: versioned at `/api/v1/`. No unversioned routes.
- **Error responses**: RFC 7807 Problem Details format.
- **Logging**: structlog with `commodity`, `position_id`, `risk_metric` as standard context keys.

---

## Key Decisions Log

Architectural decisions with broad scope live in [`docs/adr/`](docs/adr/0000-index.md) as ADRs. The table below is a quick-reference of smaller, narrower choices that don't warrant a full ADR.

| Decision | Choice | Reason |
|---|---|---|
| DB + Auth | Supabase | Zero-ops PostgreSQL, Auth, Storage, Realtime in one |
| Dep management | uv | 10–100× faster than pip, lock file, works inside Docker |
| Price scheduler | GitHub Actions Cron | Zero infra, auditable, free |
| Milho CBOT | ZC=F proxy | B3 has no free public API |
| Backend deploy | Render free tier | Acceptable cold starts for portfolio demo |
| Frontend deploy | Vercel | Best-in-class for Next.js |
| Airflow | Docker Compose local | Portfolio value without ops overhead in demo |
| VaR engine | Pure Python (numpy) | Avoids heavy ML deps, fully testable, transparent |
| Instrument model | 4 tables (physical, CBOT, basis, FX) | DB-level type safety; see [ADR-0001](docs/adr/0001-instrument-model.md) |
| Physical contract | Frame + Fixações (parent–child) | Mirrors trading workflow; see [ADR-0002](docs/adr/0002-fixacao-model.md) |
| Risk views | Flat + per-leg VaR | Capital reserve + hedge allocation; see [ADR-0003](docs/adr/0003-risk-aggregation.md) |
| Lifecycle | Explicit status + `trade_events` audit log | Compliance + backtest reconstruction |
| Options (Phase 8) | BSM / Binomial CRR / Barrier MC | Deferred from MVP; documented as V2 in BUILD_PLAN.md |
