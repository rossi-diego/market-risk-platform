# market-risk-platform — Build Plan

Phased delivery plan for the market-risk-platform MVP. Each phase has:

- **Goal** — one-line objective.
- **Deliverables** — concrete artifacts produced.
- **Prompt for Claude Code** — paste-ready into a Claude Code session at the repo root.
- **Auto-verification** — commands Claude Code runs and reports back after implementation.
- **Manual checkpoint** — things *you* validate before moving on.
- **Duration estimate** — rough effort on a weekend-warrior cadence.

Work split: **Claude Code (VSCode terminal)** drives implementation; **Cowork chat** handles Supabase MCP ops, Vercel deploys, ADR writing, and cross-system validation.

---

## Scope updates vs. original `CLAUDE.md`

The original spec said "long only, premium as a field of a physical position". This plan expands it:

1. **Long AND short** — every instrument has `side: buy | sell`.
2. **Four instrument tables** — physical, CBOT derivatives, basis forwards, FX derivatives.
3. **Physical contract = Frame + Fixações (parent–child)** — a frame is opened for an aggregate quantity and delivery window; fixações are child records that lock one or more legs (CBOT, basis, FX).
4. **Fixation modes** — `flat` (all three legs), `cbot`, `cbot_basis`, `basis`, `fx`.
5. **Derivative types** — futures, swaps, European options, American options, barrier/exotic options (last two are Phase 8, advanced tier).
6. **Lifecycle** — explicit `status` on every position (`open | partial | closed | expired`) with `trade_events` table logging fills, adjustments, and expiries.
7. **VaR computations** — flat *and* per-leg (CBOT delta, basis delta, FX delta) for all methods.
8. **Full insight set** — exposure decomposition, VaR attribution, MC fan chart, correlation matrix, margin estimate.

Phase 0 updates the canonical `CLAUDE.md` to reflect this.

---

## Phase map

| # | Phase | Output | Duration |
|---|-------|--------|----------|
| 0 | Spec alignment | `CLAUDE.md` updated + ADRs | 1–2 h |
| 1 | Repo scaffold | `backend/`, `frontend/`, tooling | 2–3 h |
| 2 | Supabase schema + RLS | 9 tables + policies + Alembic | 3–4 h |
| 3 | Domain core (pricing + exposure) | `risk/pricing.py`, `risk/exposure.py` + tests | 3–4 h |
| 4 | Price ingestion | yfinance fetcher + cron + DAG | 2–3 h |
| 5 | Position CRUD + import | FastAPI endpoints + Excel import | 4–5 h |
| 6 | Risk engine — VaR/CVaR/stress | 3 methods + ES + scenarios | 4–5 h |
| 7 | Risk engine — MC + correlation | Fan chart + Cholesky + attribution | 3–4 h |
| 8 | Options pricing (advanced) | BSM + binomial + barrier MC + Greeks | 4–6 h |
| 9 | Frontend scaffold + auth | Next.js shell + Supabase Auth | 3–4 h |
| 10 | Positions UI | 4 tabbed CRUD + frame detail + import | 5–6 h |
| 11 | Risk dashboard | 7 widgets + drill-downs | 5–6 h |
| 12 | Scenario builder + insights | Custom stress + sensitivity + PDF export | 3–4 h |
| 13 | Deploy + observability | Vercel + Render + structlog + CI | 3–4 h |

MVP ends at Phase 11. Phases 12–13 polish for portfolio quality. Phase 8 is advanced — feel free to defer.

---

## Conventions in every prompt

Every Claude Code prompt below follows this pattern:

1. **Context block** — pins the phase goal and references `CLAUDE.md` sections.
2. **Skill load** — explicit `Read` of relevant `.claude/skills/<name>/SKILL.md` files.
3. **Task list** — numbered, specific, with file paths.
4. **Verification block** — exact commands to run and format of the report.
5. **Report request** — structured output so you can eyeball pass/fail fast.

Claude Code is instructed to **stop and ask** if any task is ambiguous rather than guess. Use the checkpoints to gate progress — don't start Phase N+1 if Phase N's checkpoint failed.

---

# Phase 0 — Spec alignment

**Goal:** Update `CLAUDE.md` to match the expanded scope and record the architectural decisions.

**Deliverables:**
- `CLAUDE.md` updated (long/short, 4 instrument tables, fixações, lifecycle, 5 fixation modes, option detail)
- `docs/adr/0001-instrument-model.md` — ADR on the 4-table instrument model
- `docs/adr/0002-fixacao-model.md` — ADR on Frame + Fixações parent–child model
- `docs/adr/0003-risk-aggregation.md` — ADR on per-leg vs flat VaR methodology

**Where to run:** Cowork chat (here) — uses `engineering:architecture` skill for ADRs; `.claude/skills/commodity-price-decomposition/SKILL.md` for domain terminology.

**Prompt for Cowork:**

```
Atualize o CLAUDE.md do repo para refletir a spec expandida:

1. Substitua "long only, for now" por suporte explícito a long AND short (side: buy | sell).
2. Substitua "Position Schema" pela arquitetura de 4 tabelas de instrumento:
   - physical_frames + physical_fixations (parent-child)
   - cbot_derivatives (future | swap | european_option | american_option | barrier_option)
   - basis_forwards
   - fx_derivatives (ndf | swap | european_option | american_option | barrier_option)
3. Documente os 5 modos de fixação: flat, cbot, cbot_basis, basis, fx. Inclua uma tabela mostrando quais legs ficam abertas em cada modo.
4. Documente o lifecycle: status em {open, partial, closed, expired}, com trade_events como log de fills.
5. Atualize "Exposure Decomposition" explicando que VaR pode ser computado flat OU per-leg (CBOT delta, basis delta, FX delta).

Depois, use a skill engineering:architecture para gerar 3 ADRs em docs/adr/:
- 0001-instrument-model.md: por que 4 tabelas separadas em vez de uma genérica
- 0002-fixacao-model.md: por que Frame+Fixações em vez de posições independentes
- 0003-risk-aggregation.md: metodologia de agregação per-leg + flat

Para cada ADR siga o template Nygard (Status, Context, Decision, Consequences).
```

**Auto-verification (run after):**

```bash
# In repo root
grep -c "buy | sell" CLAUDE.md          # expect ≥1
grep -c "physical_frames" CLAUDE.md     # expect ≥1
grep -c "fixation" CLAUDE.md            # expect ≥3 (table, modes, lifecycle)
ls docs/adr/                            # expect 3 files
```

**Manual checkpoint:**

1. Abrir `CLAUDE.md` e conferir que o "Position Schema" agora lista 4 tabelas com `side: buy | sell` e `status`.
2. Abrir cada ADR em `docs/adr/` e conferir que tem as 4 seções do template Nygard.
3. Fazer `git diff CLAUDE.md` e salvar em `docs/adr/0000-index.md` a lista numerada dos ADRs.

**Duration:** 1–2 h.

---

# Phase 1 — Repo scaffold

**Goal:** Monorepo com `backend/` e `frontend/` funcionais, tooling de lint/type/test, Docker Compose local, e Supabase project criado (mas sem schema ainda).

**Deliverables:**
- `backend/pyproject.toml` + `backend/uv.lock`
- `frontend/package.json` + `frontend/next.config.mjs`
- `infra/docker-compose.yml`
- `.github/workflows/ci.yml`
- `.pre-commit-config.yaml`
- `.env.example` (backend + frontend)
- Supabase project criado via MCP, credenciais salvas localmente em `.env`

**Prompt for Claude Code:**

```
Goal: scaffold the market-risk-platform monorepo per CLAUDE.md > Repo Structure.

Read first:
- CLAUDE.md (full)
- .claude/skills/supabase-fastapi-async/SKILL.md

Tasks:

1. backend/pyproject.toml with uv:
   - python = ">=3.12,<3.13"
   - deps: fastapi>=0.115, sqlalchemy[asyncio]>=2.0, asyncpg, alembic, pydantic>=2, pydantic-settings, structlog, python-jose[cryptography], passlib[bcrypt], pandas, openpyxl, numpy, scipy, yfinance, httpx
   - dev deps: pytest, pytest-asyncio, pytest-cov, mypy, ruff, pre-commit, types-python-jose
   - [tool.ruff] line-length=100, target-version="py312", select=["E","F","I","N","W","UP","B","C4","SIM","RUF"]
   - [tool.mypy] strict=true, paths=["app"]
   - [tool.pytest.ini_options] asyncio_mode="auto"

2. backend/app/__init__.py, backend/app/main.py with a health endpoint:
   GET /api/v1/health → {"status": "ok", "version": <from env>}

3. backend/app/core/config.py with pydantic-settings loading from .env:
   SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET, DATABASE_URL, MC_SEED (default 42), LOG_LEVEL (default INFO)

4. frontend/ scaffolded with `pnpm create next-app` equivalent:
   - Next.js 14+, App Router, TypeScript, Tailwind, ESLint, src/ directory
   - Install: @supabase/supabase-js, @supabase/ssr, @tanstack/react-query, zustand, recharts, lucide-react, date-fns, zod, react-hook-form, @hookform/resolvers
   - Configure shadcn/ui (init with slate color, CSS variables, new-york style), install components: button, card, input, form, dialog, select, tabs, table, badge, toast

5. infra/docker-compose.yml with:
   - service `postgres` (postgres:16-alpine, env POSTGRES_PASSWORD/USER/DB, port 5432, volume for /var/lib/postgresql/data)
   - service `airflow` placeholder (image apache/airflow:2.9-python3.12, depends_on postgres, ports 8080)
   - Do NOT start services yet, just compose file

6. .github/workflows/ci.yml with jobs:
   - backend-lint-test: uv sync → ruff check → mypy → pytest
   - frontend-lint-build: pnpm install → pnpm lint → pnpm typecheck → pnpm build
   - trigger on pull_request and push to main

7. .pre-commit-config.yaml with:
   - ruff (backend/)
   - mypy (backend/, scoped to app/)
   - prettier (frontend/)
   - trailing-whitespace, end-of-file-fixer

8. .env.example for backend (same keys as config.py, dummy values) and frontend/.env.example (NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY, NEXT_PUBLIC_API_URL)

Verification (run after all tasks):
- cd backend && uv lock && uv sync  → expect 0 errors
- cd backend && uv run pytest --version  → expect version printed
- cd backend && uv run mypy app/ --strict  → expect "Success: no issues found"
- cd frontend && pnpm install && pnpm lint  → expect 0 lint errors
- cd frontend && pnpm typecheck  → expect 0 type errors
- cd frontend && pnpm build  → expect successful build
- pre-commit run --all-files  → report any failures
- tree -L 3 -I 'node_modules|.venv|.next'  → paste output

Report format:
## Phase 1 Report
- [ ] backend uv sync clean
- [ ] backend mypy strict clean
- [ ] frontend install clean
- [ ] frontend lint clean
- [ ] frontend typecheck clean
- [ ] frontend build clean
- [ ] pre-commit clean
- Tree:
  <paste tree output>
- Issues/notes:
  <...>

Stop and ask if anything is unclear. Do NOT invent tool versions — use latest stable as of today.
```

**After the prompt above, switch to Cowork chat and run:**

```
Use the Supabase MCP to create a new project called "market-risk-platform-dev" in region sa-east-1 (São Paulo). Get the cost, confirm with the user, then create the project. After creation:

1. get_project_url to get the API URL
2. get_publishable_keys to get anon key
3. Print these alongside the DATABASE_URL (from the project dashboard) for the user to add to backend/.env and frontend/.env.local

Do NOT commit these secrets.
```

**Manual checkpoint:**

1. `cd backend && uv run uvicorn app.main:app --reload` → abrir `http://localhost:8000/api/v1/health` → JSON com `{"status": "ok"}`.
2. `cd frontend && pnpm dev` → abrir `http://localhost:3000` → tela default do Next.js renderiza.
3. `docker compose -f infra/docker-compose.yml up -d postgres` → `docker ps` mostra postgres rodando.
4. Abrir Supabase dashboard do projeto novo → seção "Project URL" visível, "Database" com URL pronta.
5. `cat backend/.env` → preenchido com credenciais reais, NÃO commitado (`git status` confirma).

**Duration:** 2–3 h.

---

# Phase 2 — Supabase schema + RLS

**Goal:** Modelagem relacional completa das 4 famílias de instrumento + frames + fixações + trade events + prices + scenarios, com RLS por `user_id`.

**Deliverables:**
- Migration 001: base tables + enums
- Migration 002: RLS policies
- Migration 003: indexes + constraints
- `backend/app/models/*.py` (SQLAlchemy 2.0 async ORM)
- `backend/app/schemas/*.py` (Pydantic v2 in/out)
- Seed script para dados de dev

**Where to run:** Cowork chat (Supabase MCP `apply_migration` + `get_advisors`). Depois volta pro Claude Code para os models.

**Prompt for Cowork (migrations):**

```
Use Supabase MCP para aplicar migrations no projeto market-risk-platform-dev.

Skill: .claude/skills/supabase-fastapi-async/SKILL.md (se já carregada) ou leia agora.

Schema objetivo:

-- Enums
CREATE TYPE commodity AS ENUM ('soja', 'milho');
CREATE TYPE side AS ENUM ('buy', 'sell');
CREATE TYPE position_status AS ENUM ('open', 'partial', 'closed', 'expired');
CREATE TYPE fixation_mode AS ENUM ('flat', 'cbot', 'cbot_basis', 'basis', 'fx');
CREATE TYPE cbot_instrument AS ENUM ('future', 'swap', 'european_option', 'american_option', 'barrier_option');
CREATE TYPE fx_instrument AS ENUM ('ndf', 'swap', 'european_option', 'american_option', 'barrier_option');
CREATE TYPE option_type AS ENUM ('call', 'put');
CREATE TYPE barrier_type AS ENUM ('up_and_in','up_and_out','down_and_in','down_and_out');
CREATE TYPE price_source AS ENUM ('YFINANCE_CBOT','YFINANCE_FX','CBOT_PROXY_YFINANCE','B3_OFFICIAL','USER_MANUAL');

-- prices: time series de CBOT, FX e basis observados
CREATE TABLE prices (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  observed_at timestamptz NOT NULL,
  instrument text NOT NULL,  -- 'ZS=F','ZC=F','USDBRL=X','BASIS_SOJA_SPOT', etc.
  commodity commodity,
  value numeric(18,6) NOT NULL,
  unit text NOT NULL,  -- 'USc/bu','BRL/USD','USD/bu'
  price_source price_source NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(observed_at, instrument)
);
CREATE INDEX prices_instrument_observed_idx ON prices(instrument, observed_at DESC);

-- physical_frames: contrato físico "guarda-chuva"
CREATE TABLE physical_frames (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id),
  commodity commodity NOT NULL,
  side side NOT NULL,
  quantity_tons numeric(18,4) NOT NULL CHECK (quantity_tons > 0),
  delivery_start date NOT NULL,
  delivery_end date NOT NULL,
  counterparty text,
  status position_status NOT NULL DEFAULT 'open',
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- physical_fixations: fills de fixação sobre um frame
CREATE TABLE physical_fixations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  frame_id uuid NOT NULL REFERENCES physical_frames(id) ON DELETE CASCADE,
  fixation_mode fixation_mode NOT NULL,
  quantity_tons numeric(18,4) NOT NULL CHECK (quantity_tons > 0),
  fixation_date date NOT NULL,
  cbot_fixed numeric(18,6),       -- USc/bu, NULL se esse leg não foi fixado
  basis_fixed numeric(18,6),      -- USD/bu
  fx_fixed numeric(18,6),         -- BRL/USD
  reference_cbot_contract text,   -- ex: 'ZSK26'
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (
    (fixation_mode = 'flat' AND cbot_fixed IS NOT NULL AND basis_fixed IS NOT NULL AND fx_fixed IS NOT NULL)
    OR (fixation_mode = 'cbot' AND cbot_fixed IS NOT NULL AND basis_fixed IS NULL AND fx_fixed IS NULL)
    OR (fixation_mode = 'cbot_basis' AND cbot_fixed IS NOT NULL AND basis_fixed IS NOT NULL AND fx_fixed IS NULL)
    OR (fixation_mode = 'basis' AND basis_fixed IS NOT NULL AND cbot_fixed IS NULL AND fx_fixed IS NULL)
    OR (fixation_mode = 'fx' AND fx_fixed IS NOT NULL AND cbot_fixed IS NULL AND basis_fixed IS NULL)
  )
);
CREATE INDEX physical_fixations_frame_idx ON physical_fixations(frame_id);

-- cbot_derivatives
CREATE TABLE cbot_derivatives (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id),
  commodity commodity NOT NULL,
  instrument cbot_instrument NOT NULL,
  side side NOT NULL,
  contract text NOT NULL,              -- 'ZSK26','ZCN26'
  quantity_contracts numeric(18,4) NOT NULL CHECK (quantity_contracts > 0),
  trade_date date NOT NULL,
  trade_price numeric(18,6) NOT NULL,  -- USc/bu entry price
  maturity_date date NOT NULL,
  -- option-specific (NULL se não é option)
  option_type option_type,
  strike numeric(18,6),
  -- barrier-specific
  barrier_type barrier_type,
  barrier_level numeric(18,6),
  rebate numeric(18,6),
  status position_status NOT NULL DEFAULT 'open',
  counterparty text,
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- basis_forwards
CREATE TABLE basis_forwards (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id),
  commodity commodity NOT NULL,
  side side NOT NULL,
  quantity_tons numeric(18,4) NOT NULL CHECK (quantity_tons > 0),
  trade_date date NOT NULL,
  basis_price numeric(18,6) NOT NULL,  -- USD/bu
  delivery_date date NOT NULL,
  reference_cbot_contract text NOT NULL,
  status position_status NOT NULL DEFAULT 'open',
  counterparty text,
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- fx_derivatives
CREATE TABLE fx_derivatives (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id),
  instrument fx_instrument NOT NULL,
  side side NOT NULL,
  notional_usd numeric(18,2) NOT NULL CHECK (notional_usd > 0),
  trade_date date NOT NULL,
  trade_rate numeric(18,6) NOT NULL,   -- BRL/USD entry
  maturity_date date NOT NULL,
  option_type option_type,
  strike numeric(18,6),
  barrier_type barrier_type,
  barrier_level numeric(18,6),
  rebate numeric(18,6),
  status position_status NOT NULL DEFAULT 'open',
  counterparty text,
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- trade_events: audit trail / lifecycle log
CREATE TABLE trade_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id),
  event_type text NOT NULL,   -- 'open','fill','partial_close','close','expire','adjust'
  instrument_table text NOT NULL,  -- 'physical_frames','cbot_derivatives','basis_forwards','fx_derivatives'
  instrument_id uuid NOT NULL,
  quantity numeric(18,4),
  price numeric(18,6),
  event_date timestamptz NOT NULL DEFAULT now(),
  payload jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX trade_events_instrument_idx ON trade_events(instrument_table, instrument_id, event_date DESC);

-- mtm_premiums: global config per commodity, editable in UI
CREATE TABLE mtm_premiums (
  commodity commodity PRIMARY KEY,
  premium_usd_bu numeric(18,6) NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now(),
  updated_by uuid REFERENCES auth.users(id)
);

-- scenarios: user-defined stress scenarios
CREATE TABLE scenarios (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id),
  name text NOT NULL,
  description text,
  cbot_soja_shock_pct numeric(6,4) NOT NULL DEFAULT 0,
  cbot_milho_shock_pct numeric(6,4) NOT NULL DEFAULT 0,
  basis_soja_shock_pct numeric(6,4) NOT NULL DEFAULT 0,
  basis_milho_shock_pct numeric(6,4) NOT NULL DEFAULT 0,
  fx_shock_pct numeric(6,4) NOT NULL DEFAULT 0,
  is_historical boolean NOT NULL DEFAULT false,
  source_period text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(user_id, name)
);

Depois de aplicar, aplique 2 migrations adicionais:

Migration 002 - RLS: enable RLS em todas as tabelas de usuário (physical_frames, cbot_derivatives, basis_forwards, fx_derivatives, trade_events, scenarios) com policy:
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id)
Physical_fixations herda via frame_id → EXISTS (SELECT 1 FROM physical_frames WHERE id = frame_id AND user_id = auth.uid()).
prices, mtm_premiums são públicos read-only para auth users (policy FOR SELECT USING (auth.role() = 'authenticated')).

Migration 003 - seed historical scenarios (is_historical=true, user_id=NULL skip — faça separado via mtm_premiums insert + scenarios template):
  Insert os 4 scenarios do CLAUDE.md (2008 GFC, 2012 drought, 2020 COVID, 2022 Ukraine) como templates (pode duplicar para cada user depois) — simplifica: cria uma tabela `scenarios_templates` sem user_id para os 4 built-ins e RLS policy FOR SELECT TO authenticated.

Após aplicar as 3 migrations, rode:
- list_tables schemas=['public'] verbose=true → confirme 9 tables (prices, physical_frames, physical_fixations, cbot_derivatives, basis_forwards, fx_derivatives, trade_events, mtm_premiums, scenarios, scenarios_templates = 10)
- get_advisors type=security → listar issues. Deve estar clean se RLS foi aplicada em todas user tables
- get_advisors type=performance → listar issues

Report back com a lista de tabelas, RLS status, e advisors.
```

**Prompt for Claude Code (ORM + schemas, run after migrations applied):**

```
Context: Supabase schema is in place (9 tables + 1 template). Generate SQLAlchemy models and Pydantic schemas mirroring it.

Read first:
- CLAUDE.md
- .claude/skills/supabase-fastapi-async/SKILL.md
- docs/adr/0001-instrument-model.md
- docs/adr/0002-fixacao-model.md

Tasks:

1. backend/app/models/base.py: Base = DeclarativeBase, with common mixins (TimestampMixin with created_at/updated_at).

2. backend/app/models/*.py — one file per domain family:
   - prices.py (Price)
   - physical.py (PhysicalFrame, PhysicalFixation)
   - cbot.py (CBOTDerivative)
   - basis.py (BasisForward)
   - fx.py (FXDerivative)
   - events.py (TradeEvent)
   - config.py (MTMPremium, ScenarioTemplate, Scenario)
   All use SQLAlchemy 2.0 typed syntax (Mapped[...], mapped_column). Enums via sqlalchemy.Enum(native_enum=False) so Postgres native enums are used.

3. backend/app/schemas/*.py — Pydantic v2, one file per domain:
   - Each has *In (for POST/PUT), *Out (for GET), *Update (for PATCH)
   - Decimal fields typed as Decimal, enum fields as Literal types matching DB enums
   - field_validator on fixations to mirror the DB CHECK constraint (fail fast with clear error)
   - ConfigDict(from_attributes=True) on Out schemas

4. backend/app/core/db.py: async engine factory from config.DATABASE_URL, async_sessionmaker, get_session() dependency for FastAPI.

5. backend/alembic/ initialized with env.py pointing at app.core.db and app.models.Base.metadata. Generate a baseline revision marked as "baseline — schema created via Supabase Studio" (do NOT autogenerate — the schema already exists). Lock it so future diffs are captured.

6. backend/tests/unit/test_models.py: parametrized tests that instantiate each model with valid/invalid data, check enum coercion, check Pydantic validator on fixations (all 5 modes).

Verification:
- uv run mypy app/ --strict → 0 errors
- uv run pytest backend/tests/unit/test_models.py -v → all pass
- uv run python -c "from app.core.db import engine; import asyncio; asyncio.run(engine.dispose())" → silent success
- Generate a DB connection test:
   uv run python scripts/db_smoke.py  (create this script: opens session, does SELECT 1 from prices, closes)

Report:
## Phase 2 Report (ORM side)
- [ ] mypy strict clean
- [ ] model tests pass (N/N)
- [ ] DB smoke test OK
- [ ] alembic baseline created
- Files created (list)
- Notes

Stop and ask if anything is unclear.
```

**Manual checkpoint:**

1. No Supabase Studio, abrir Table Editor → conferir as 10 tabelas, com RLS badge verde em todas as user-scoped.
2. Tentar inserir uma `physical_fixation` com `fixation_mode='cbot'` e `basis_fixed` preenchido → DB deve rejeitar (CHECK constraint).
3. Rodar `backend/scripts/db_smoke.py` → sai sem erro.
4. `uv run alembic current` → mostra o baseline revision.
5. Advisors no Cowork: 0 security issues em user tables.

**Duration:** 3–4 h.

---

# Phase 3 — Domain core: pricing + exposure

**Goal:** Implementar as funções puras de precificação e decomposição de exposição. Toda matemática de conversão de unidade vive em `risk/pricing.py`. `risk/exposure.py` agrega por leg.

**Deliverables:**
- `backend/app/risk/pricing.py` (formula BRL/ton, unit conversions, funções puras)
- `backend/app/risk/exposure.py` (computa open exposure per leg para um frame dado as fixações)
- `backend/app/risk/types.py` (dataclasses/TypedDict para ExposureBreakdown, FrameExposure)
- Testes unitários 100% de coverage nas funções puras

**Prompt for Claude Code:**

```
Context: Implement the core pricing and exposure aggregation logic. All formulas from CLAUDE.md > Price Formation Model must live in risk/pricing.py. No inline conversion math outside this module.

Read first:
- CLAUDE.md (Price Formation Model section)
- .claude/skills/commodity-price-decomposition/SKILL.md
- .claude/skills/risk-engine-patterns/SKILL.md

Tasks:

1. backend/app/risk/pricing.py — pure functions with type hints and docstrings:
   - TONS_TO_BUSHELS = {"soja": Decimal("36.744"), "milho": Decimal("56.0")}
   - def price_brl_ton(commodity, cbot_uscbu, fx_brl_usd, premium_usd_bu) -> Decimal
   - def mtm_value_brl(commodity, quantity_tons, cbot, fx, premium) -> Decimal
   - def cbot_delta_brl_ton(commodity, fx) -> Decimal  # ΔP&L per 1 USc/bu CBOT move, in BRL/ton
   - def fx_delta_brl_ton(commodity, cbot, premium) -> Decimal  # ΔP&L per 0.01 BRL/USD move
   - def premium_delta_brl_ton(commodity, fx) -> Decimal  # ΔP&L per 1 USD/bu premium move
   - All return Decimal (no floats in financial math).

2. backend/app/risk/exposure.py:
   - @dataclass(frozen=True, slots=True) class LegExposure: cbot_qty_tons, basis_qty_tons, fx_qty_tons (Decimal, >=0)
   - def open_exposure_frame(frame: PhysicalFrame, fixations: list[PhysicalFixation]) -> LegExposure
     - For each leg (cbot, basis, fx), sum quantity_tons of fixations that locked that leg
     - Return LegExposure(qty_tons - sum_locked_by_leg) per leg
     - Remember: fixation_mode=flat locks all 3; cbot=only cbot; cbot_basis=cbot+basis; basis=only basis; fx=only fx
   - def aggregate_exposure(frames_with_fixations, cbot_derivs, basis_fwds, fx_derivs) -> AggregateExposure
     - Sum open exposures per commodity + leg
     - Physical buy → long all 3 legs (price gain if market goes up)
     - Physical sell → short all 3 legs
     - CBOT derivative: buy future = long CBOT delta; sell = short. Options need delta from pricing engine (stub in Phase 3, implement in Phase 8). For now raise NotImplementedError for options.
     - Basis forward: same side convention.
     - FX derivative: adds/subtracts FX delta only.

3. backend/app/risk/types.py:
   - TypedDict / dataclass definitions:
     - ExposureBreakdown (per commodity, per leg, gross long, gross short, net)
     - FrameExposure (frame_id, quantity, locked per leg, open per leg)
     - AggregateExposure (dict[commodity, dict[leg, Decimal]])

4. backend/tests/unit/risk/test_pricing.py — parametrized tests:
   - price_brl_ton for soja: CBOT=1000 USc/bu, FX=5.00, premium=0.50 → expected value; assert to 6 decimals
   - price_brl_ton for milho: CBOT=400 USc/bu, FX=5.00, premium=0.30 → expected value
   - cbot_delta_brl_ton for soja at FX=5.00 → expected = 5.00/100/36.744 = 0.01361... (verify by hand)
   - symmetry: sum of 3 deltas × shock size reconstructs total P&L change within rounding

5. backend/tests/unit/risk/test_exposure.py:
   - Frame 1000 tons buy, 0 fixations → LegExposure(1000, 1000, 1000)
   - Frame 1000 tons buy, 1 fixation mode=flat 300 tons → (700, 700, 700)
   - Frame 1000 tons buy, 1 fixation mode=cbot 300 + 1 mode=fx 500 → (700, 1000, 500)
   - Frame 1000 tons buy, 1 fixation mode=cbot_basis 400 → (600, 600, 1000)
   - Over-fixing fails loud: total locked per leg cannot exceed frame.quantity_tons → raise DomainError

6. Configure pytest-cov: fail if coverage on risk/ module <95%.

Verification:
- uv run mypy app/risk --strict → 0 errors
- uv run pytest backend/tests/unit/risk/ -v --cov=app.risk --cov-report=term-missing → all pass, coverage >=95%
- uv run python -c "from app.risk.pricing import price_brl_ton; from decimal import Decimal; print(price_brl_ton('soja', Decimal('1000'), Decimal('5'), Decimal('0.5')))" → sanity print

Report:
## Phase 3 Report
- [ ] mypy strict clean on risk/
- [ ] pytest pass (N/N)
- [ ] coverage on risk/ = XX%
- Test count by file
- Notes

Do NOT implement option delta here — that comes in Phase 8. Raise NotImplementedError for options.
```

**Manual checkpoint:**

1. Abrir `backend/app/risk/pricing.py` e conferir que a fórmula do CLAUDE.md está implementada literalmente (não há math inline fora disso).
2. Rodar a conta à mão: 1000 USc/bu CBOT + 5.00 FX + 0.50 USD/bu premium para soja → price_brl_ton deve bater com sua calculadora.
3. `pytest --cov=app.risk` → coverage ≥95% visível no terminal.
4. Inspecionar `test_exposure.py` → os cenários de fixação parcial estão corretos (especialmente o `cbot_basis` travando 2 legs).

**Duration:** 3–4 h.

---

# Phase 4 — Price ingestion

**Goal:** Buscar `ZS=F`, `ZC=F`, `USDBRL=X` via yfinance às 18h BRT e fazer upsert em `prices`. Dois caminhos de produção: GitHub Actions cron (primário) e Airflow DAG (local, portfolio).

**Deliverables:**
- `backend/app/services/price_ingestion.py`
- `backend/scripts/fetch_prices.py` (CLI entrypoint)
- `.github/workflows/price_update.yml`
- `infra/airflow/dags/commodity_price_pipeline.py`
- Integration test que mocka yfinance e valida upsert

**Prompt for Claude Code:**

```
Goal: implement the price ingestion pipeline per CLAUDE.md > Data Sources & Update Schedule.

Read first:
- CLAUDE.md (Data Sources section)
- .claude/skills/airflow-price-pipeline/SKILL.md
- .claude/skills/commodity-price-decomposition/SKILL.md (for price_source flags)

Tasks:

1. backend/app/services/price_ingestion.py:
   - async def fetch_cbot_soja() -> PriceRecord  (yfinance ZS=F, price_source=YFINANCE_CBOT)
   - async def fetch_cbot_milho() -> PriceRecord  (yfinance ZC=F, price_source=CBOT_PROXY_YFINANCE)
   - async def fetch_fx_usdbrl() -> PriceRecord  (yfinance USDBRL=X, price_source=YFINANCE_FX)
   - async def validate_records(records: list[PriceRecord]) -> list[PriceRecord]
     - reject if value <= 0
     - reject if timestamp older than last valid by >5 trading days (stale feed)
     - log structured (structlog) with commodity, instrument, value
   - async def upsert_prices(session, records) -> int (count upserted)
     - ON CONFLICT (observed_at, instrument) DO UPDATE

2. backend/scripts/fetch_prices.py:
   - CLI with argparse: --dry-run (no upsert, just print), --date YYYY-MM-DD (override "now")
   - Main calls fetch_all → validate → upsert → logs summary
   - Exit code 0 on success, 1 on any failure (for cron to alert)

3. .github/workflows/price_update.yml:
   - schedule: cron '0 21 * * 1-5'  # 21h UTC = 18h BRT
   - manual workflow_dispatch with inputs: date (optional)
   - secrets: SUPABASE_DB_URL, SUPABASE_SERVICE_ROLE_KEY
   - uses uv with cache, runs `uv run python backend/scripts/fetch_prices.py`
   - on failure: create issue via gh CLI with logs attached

4. infra/airflow/dags/commodity_price_pipeline.py:
   - DAG id "commodity_price_pipeline", schedule "0 18 * * 1-5", tz America/Sao_Paulo
   - Tasks: fetch_soy >> fetch_corn >> fetch_fx >> validate >> upsert >> trigger_mtm_recalc
   - Use TaskFlow API, shared session via PostgresHook (or direct asyncpg)
   - trigger_mtm_recalc is a stub HTTP POST to backend /api/v1/risk/recalculate (implemented Phase 6)

5. backend/tests/integration/test_price_ingestion.py:
   - Uses pytest-mock to monkeypatch yfinance.Ticker
   - Asserts upsert idempotent: running twice with same timestamp doesn't duplicate
   - Asserts price_source flag set correctly per ticker
   - Asserts stale detection works

Verification:
- uv run pytest backend/tests/integration/test_price_ingestion.py -v → pass
- uv run python backend/scripts/fetch_prices.py --dry-run → prints 3 records without errors
- uv run python backend/scripts/fetch_prices.py → inserts 3 rows (verify via supabase execute_sql SELECT count(*) FROM prices WHERE observed_at::date = current_date)
- Validate GitHub Actions YAML: gh workflow list (after pushing)
- Airflow DAG: docker compose -f infra/docker-compose.yml up airflow, open localhost:8080, DAG appears with 5 tasks

Report:
## Phase 4 Report
- [ ] yfinance fetchers work (dry-run output attached)
- [ ] upsert idempotent (test passes)
- [ ] workflow YAML lints clean
- [ ] Airflow DAG loads (screenshot or list of tasks)
- Row count in prices after real run
- Notes
```

**Manual checkpoint:**

1. `uv run python backend/scripts/fetch_prices.py --dry-run` → 3 records impressos com valores próximos ao CBOT/FX atual.
2. No Supabase Studio → tabela `prices` com ≥3 linhas do dia de hoje, `price_source` correto.
3. Rodar o script 2× seguidas → contagem não duplica (upsert funcionou).
4. `docker compose up airflow` → abrir `localhost:8080` → DAG `commodity_price_pipeline` aparece com 5 tasks, sem erro de parsing.
5. Fazer push do `.github/workflows/price_update.yml` e trigar manualmente via `gh workflow run price_update.yml` → workflow passa verde.

**Duration:** 2–3 h.

---

# Phase 5 — Position CRUD + Excel import

**Goal:** Endpoints FastAPI completos para as 4 famílias de instrumento + fixações + frames. Importação de planilha Excel com preview.

**Deliverables:**
- `backend/app/api/v1/physical.py` (frames + fixations)
- `backend/app/api/v1/cbot.py`, `basis.py`, `fx.py`
- `backend/app/api/v1/imports.py` (Excel/CSV upload)
- `backend/app/core/security.py` (Supabase JWT validation dependency)
- Integration tests com test user real

**Prompt for Claude Code:**

```
Goal: implement FastAPI CRUD endpoints for all 4 instrument families + frame/fixation endpoints + Excel import.

Read first:
- CLAUDE.md (Repo Structure, Conventions)
- .claude/skills/supabase-fastapi-async/SKILL.md

Tasks:

1. backend/app/core/security.py:
   - get_current_user(authorization: str) dependency validates JWT against SUPABASE_JWT_SECRET (HS256). Returns User(id=uuid, email=str).
   - All endpoints below require this dependency.

2. backend/app/api/v1/physical.py:
   - GET /physical/frames → list current user's frames + aggregated fixations
   - POST /physical/frames → create frame
   - GET /physical/frames/{id} → frame detail including all fixations
   - PATCH /physical/frames/{id} → update counterparty/notes/status (not quantity)
   - POST /physical/frames/{id}/fixations → create fixation, validate:
     - user owns frame
     - total locked per leg after this fixation does not exceed frame.quantity_tons (per leg, per fixation_mode)
     - fixation_date >= frame.created_at
   - DELETE /physical/fixations/{id} → remove fixation; recompute frame.status (open/partial/closed) via trigger or service

3. backend/app/api/v1/cbot.py, basis.py, fx.py:
   - GET /{scope} (list), POST (create), GET /{id}, PATCH /{id}, DELETE /{id}
   - Validate option fields present when instrument is an option type
   - Validate barrier fields when instrument is barrier_option

4. backend/app/api/v1/imports.py:
   - POST /imports/preview (multipart/form-data with .xlsx):
     - parse sheets named "physical_frames","physical_fixations","cbot","basis","fx"
     - return rows parsed + validation errors per row (Pydantic)
     - DOES NOT write to DB
   - POST /imports/commit:
     - takes the validated payload + import_id (idempotency key)
     - writes in a single transaction; all-or-nothing
     - logs to trade_events with event_type='open'

5. backend/app/services/imports.py:
   - Use pandas + openpyxl to read Excel
   - Map column names (Portuguese or English) to schema fields via an alias dict
   - Coerce dates, decimals, enums with clear errors

6. backend/app/services/status_recompute.py:
   - Given a frame, recompute status based on fixations:
     - if no fixations: open
     - if sum of locked tons per leg < frame quantity for at least one leg: partial
     - if all 3 legs fully locked: closed
     - (expired set by a separate cron when delivery_end passes)

7. docs/example_import.xlsx — generate a valid example file with 3 rows per sheet.

8. backend/tests/integration/test_positions_crud.py:
   - Fixture that creates a test user + JWT token (use Supabase admin API with service_role key)
   - Smoke for each endpoint: create, list, read, update, delete
   - test_fixation_over_lock: creates a 1000 ton frame, fixes 600 cbot + 500 cbot → expect 409 on second
   - test_import_preview_validation_errors: malformed row returns errors not DB write
   - test_import_commit_atomic: 10 rows with 1 invalid → rollback, no rows inserted

Verification:
- uv run pytest backend/tests/integration/test_positions_crud.py -v → all pass
- uv run uvicorn app.main:app (manual): hit each endpoint with httpie or curl (authorized)
- openapi.json generated at /api/v1/openapi.json has all endpoints documented

Report:
## Phase 5 Report
- [ ] All integration tests pass (N/N)
- [ ] Auth dependency rejects missing/invalid JWT
- [ ] Over-fix validation returns 409
- [ ] Import preview + commit transactional
- [ ] example_import.xlsx valid
- Endpoints count (grep decorator): X
- Notes
```

**Manual checkpoint:**

1. Usar o Swagger UI em `http://localhost:8000/api/v1/docs` → autenticar com JWT de teste → criar 1 frame de 1000 ton soja buy, 3 fixações (1 cbot, 1 basis, 1 fx parciais). Conferir `GET /frames/{id}` retorna frame com fixações aninhadas.
2. Tentar fixação que ultrapassa → resposta 409 com mensagem clara.
3. Upload do `docs/example_import.xlsx` via `/imports/preview` → devolve rows parseadas + 0 errors. `/imports/commit` insere tudo.
4. Checar no Supabase Studio que `trade_events` registrou 1 evento por posição criada.

**Duration:** 4–5 h.

---

# Phase 6 — Risk engine: VaR / CVaR / stress

**Goal:** Implementar as 3 metodologias de VaR (histórica, paramétrica, Monte Carlo básica) + CVaR + stress testing histórico e custom, com saída per-leg e flat.

**Deliverables:**
- `backend/app/risk/var.py`, `cvar.py`, `stress.py`, `returns.py`
- Endpoints `/api/v1/risk/var`, `/risk/cvar`, `/risk/stress`
- Testes com distribuições sintéticas de validação

**Prompt for Claude Code:**

```
Goal: implement risk metrics per CLAUDE.md > Risk Metrics — Methodology Reference.

Read first:
- CLAUDE.md (Risk Metrics section)
- .claude/skills/risk-engine-patterns/SKILL.md
- .claude/skills/risk-engine-patterns/references/stress_scenarios.md
- docs/adr/0003-risk-aggregation.md

Tasks:

1. backend/app/risk/returns.py:
   - def compute_returns(prices_df: pd.DataFrame, kind: Literal['log','simple']) -> pd.DataFrame
   - def align_multi_series(series_dict) -> pd.DataFrame  # outer-join + forward fill max 1 day
   - def rolling_window(df, days=252) -> pd.DataFrame

2. backend/app/risk/var.py — three methods, each returns VaRResult(method, confidence, horizon_days, value_brl, per_leg={cbot,basis,fx}):
   - historical_var(returns, weights, confidence=0.95, horizon_days=1, window=252)
   - parametric_var(returns, weights, confidence=0.95, horizon_days=1) — assumes normal; sigma × sqrt(horizon) × z
   - monte_carlo_var(returns, weights, confidence=0.95, horizon_days=1, n_paths=10_000, seed=config.MC_SEED)
   - All accept a PortfolioExposure object (exposure per commodity per leg from Phase 3)
   - Per-leg VaR: same methods but applied separately to each leg's weighted returns

3. backend/app/risk/cvar.py:
   - expected_shortfall(returns, weights, confidence, horizon) = mean of returns beyond VaR threshold
   - Per-leg version

4. backend/app/risk/stress.py:
   - apply_scenario(exposure, scenario: Scenario) → StressResult(total_pnl, per_leg_pnl, per_commodity_pnl)
   - HISTORICAL_SCENARIOS: built-in table from CLAUDE.md (2008 GFC, 2012 drought, 2020 COVID, 2022 Ukraine)
   - run_all_historical(exposure) returns list[StressResult]

5. backend/app/api/v1/risk.py:
   - POST /risk/var {method, confidence, horizon_days, per_leg: bool} → VaRResult
   - POST /risk/cvar {...} → CVaRResult
   - POST /risk/stress/historical → list[StressResult]
   - POST /risk/stress/custom {scenario_id or inline scenario} → StressResult
   - All read current user's open positions, compute exposure, then apply metric

6. backend/tests/unit/risk/test_var.py:
   - Synthetic data: 1000 days of N(0, 0.01) returns → parametric VaR 95% ≈ 1.645 * 0.01 * exposure
   - Historical VaR on same data matches parametric within 10% (finite sample)
   - MC VaR with seed=42 is reproducible: same call twice returns exact same number
   - Per-leg VaR sums to flat VaR within rounding (component additive on simple normal)
   - Scale √h: VaR 10-day = VaR 1-day × sqrt(10) for parametric

7. backend/tests/unit/risk/test_cvar.py:
   - CVaR ≥ VaR for same confidence (always)
   - On normal returns, ES 97.5% ≈ parametric formula φ(z)/(1-α) * σ

8. backend/tests/unit/risk/test_stress.py:
   - 2008 GFC on a 1000 ton soja long, CBOT=1000, FX=5.00, premium=0.5 → verify P&L manually and match
   - All 4 historical scenarios produce non-zero results on a sample portfolio

Verification:
- uv run pytest backend/tests/unit/risk/ -v --cov=app.risk --cov-report=term-missing → all pass, coverage >=90%
- uv run mypy app/risk --strict → 0 errors
- Start API, POST /risk/var with a sample portfolio → valid response, value_brl > 0

Report:
## Phase 6 Report
- [ ] All risk unit tests pass (N/N)
- [ ] Coverage on risk/ = XX%
- [ ] MC reproducibility verified
- [ ] Historical scenarios match manual calc
- Endpoints response time (hit /risk/var twice, report p50)
- Notes
```

**Manual checkpoint:**

1. No Swagger UI, POST `/risk/var` com método histórico sobre seu portfolio de teste → resposta com `value_brl` e `per_leg` preenchidos.
2. Mudar `confidence` de 0.95 para 0.99 → valor deve crescer.
3. Rodar `/risk/stress/historical` → 4 scenarios com P&L não-zero, sinais consistentes com a direção do portfolio.
4. Rerodar `/risk/var` com method=monte_carlo duas vezes → números idênticos (seed).

**Duration:** 4–5 h.

---

# Phase 7 — Risk engine: MC + correlation + attribution

**Goal:** Monte Carlo correlacionado (Cholesky) para fan chart, matriz de correlação, VaR attribution por posição.

**Deliverables:**
- `backend/app/risk/mc.py` (correlated MC, fan chart paths)
- `backend/app/risk/correlation.py`
- `backend/app/risk/attribution.py` (component VaR)
- Endpoints `/risk/mc/fan`, `/risk/correlation`, `/risk/attribution`

**Prompt for Claude Code:**

```
Goal: advanced risk — correlated MC + fan chart + correlation matrix + position-level VaR attribution.

Read first:
- .claude/skills/risk-engine-patterns/SKILL.md
- docs/adr/0003-risk-aggregation.md

Tasks:

1. backend/app/risk/correlation.py:
   - correlation_matrix(returns_df) → np.ndarray + index names; check positive semi-definite
   - cholesky(corr) returning L such that LL' ≈ corr (with PSD guard: nearest_psd if not)

2. backend/app/risk/mc.py:
   - simulate_paths(mu, sigma, corr, n_paths, n_steps, dt, seed) → np.ndarray of shape (n_paths, n_steps, n_factors)
   - Factors: cbot_soja, cbot_milho, basis_soja, basis_milho, fx
   - Uses Cholesky-correlated GBM
   - fan_chart_paths(exposure, mu, sigma, corr, horizon_days=10, n_paths=10_000) → percentiles [5,25,50,75,95] of portfolio P&L at each day

3. backend/app/risk/attribution.py:
   - component_var(positions, returns, method='parametric', confidence=0.95) → list[PositionContribution]
     - For parametric: component_var_i = (w_i × sigma_i × rho_i,p × VaR_p) / sigma_p
     - sum of components = total VaR (property test)
   - marginal_var(position, portfolio, shift=0.01) → incremental VaR

4. backend/app/api/v1/risk.py adds:
   - POST /risk/mc/fan → {percentiles: {5: [...], 25: [...], ...}, total_paths, horizon}
   - GET /risk/correlation?window=252 → {matrix, names}
   - POST /risk/attribution → list of (position_id, contribution_brl, share_pct)

5. Tests:
   - Correlation matrix on known inputs (2 perfectly correlated series → rho ≈ 1)
   - Cholesky on a PSD matrix reproduces corr: np.allclose(L @ L.T, corr)
   - Sum of component_var ≈ total VaR within 1%
   - MC fan chart percentiles are monotone (5 ≤ 25 ≤ 50 ≤ 75 ≤ 95)
   - Reproducibility with seed

Verification:
- uv run pytest backend/tests/unit/risk/ -v → all pass
- uv run mypy app/risk --strict → clean
- POST /risk/mc/fan → response < 2s for 10k paths × 10 days × 5 factors

Report standard format.
```

**Manual checkpoint:**

1. POST `/risk/mc/fan` → JSON com 5 arrays de 10 elementos cada (horizon=10 dias).
2. GET `/risk/correlation` → matriz 5×5 simétrica, diagonal 1.0.
3. POST `/risk/attribution` → soma das contribuições ≈ total VaR (tolerância 1%).

**Duration:** 3–4 h.

---

# Phase 8 — Options pricing (ADVANCED, opcional para MVP)

**Goal:** Precificação e Greeks para opções europeias (Black-Scholes), americanas (binomial Cox-Ross-Rubinstein), e barrier options (Monte Carlo com path monitoring).

**Esta fase é pesada. Para MVP do portfolio, pode ser escopada OUT e documentada como "V2 feature" em `docs/adr/0004-options-pricing-deferred.md`. Se manter, ~4–6 h.**

**Deliverables:**
- `backend/app/risk/options/bsm.py` (Black-Scholes-Merton, Greeks)
- `backend/app/risk/options/binomial.py` (CRR para americanas)
- `backend/app/risk/options/barrier.py` (MC com barreiras)
- `backend/app/risk/options/greeks.py` (delta/gamma/vega/theta/rho para todos os tipos)
- Margin estimator para futures (SPAN simplificado ou initial margin lookup)

**Prompt for Claude Code:** (expandir analogamente às fases anteriores, com checks de put-call parity para BSM, convergência binomial com N steps, e validação de barrier MC contra fórmula analítica para casos sem rebate)

**Manual checkpoint:**

1. Put-call parity: BSM put + stock = call + PV(strike) para mesmo K, T, σ, r, q.
2. Binomial converge para BSM quando N=1000 steps.
3. Delta call ∈ (0, 1), delta put ∈ (-1, 0).
4. Up-and-out call com barrier = S ✕ 10 → ≈ vanilla call.

**Duration:** 4–6 h (ou diferir para V2).

---

# Phase 9 — Frontend scaffold + auth

**Goal:** Next.js 14 App Router rodando, Supabase Auth integrada, layout com sidebar, typed API client gerado do OpenAPI.

**Deliverables:**
- `frontend/src/app/(auth)/login`, `(auth)/signup`
- `frontend/src/app/(dashboard)/layout.tsx` — sidebar + top bar
- `frontend/src/lib/supabase/client.ts`, `server.ts`
- `frontend/src/lib/api/` — openapi-typescript generated types + fetch wrapper
- Middleware de auth redirect

**Prompt for Claude Code:**

```
Goal: Next.js 14 App Router shell with Supabase Auth and typed API client. Professional, clean UX.

Design principles:
- Follow shadcn/ui defaults, new-york style. No custom CSS unless necessary.
- Sidebar collapsible, keyboard accessible (Cmd+B toggle). Logo + 4 nav items: Dashboard, Positions, Risk, Scenarios.
- Top bar: breadcrumbs + user menu + theme toggle (dark by default).
- Loading states: Skeleton components everywhere, not spinners.
- Empty states: friendly + CTA button ("No positions yet — create your first one").
- Toasts via shadcn/ui sonner.
- Accessible: focus rings, aria-labels, keyboard navigation on all interactive elements.

Read first:
- CLAUDE.md (Stack > Frontend)

Tasks:

1. frontend/src/lib/supabase/{client,server,middleware}.ts using @supabase/ssr (cookie-based sessions).

2. frontend/src/app/(auth)/login/page.tsx + signup/page.tsx:
   - email/password + magic link option
   - react-hook-form + zod validation
   - Post-login redirect to /dashboard

3. frontend/middleware.ts: protect /dashboard/* and /positions/*, /risk/*, /scenarios/*. Redirect to /login with ?next= param.

4. frontend/src/app/(dashboard)/layout.tsx:
   - Sidebar (shadcn ui sidebar pattern, collapsible, Cmd+B)
   - Top bar with breadcrumbs from pathname
   - User menu dropdown: email, "Sign out"
   - Theme toggle (next-themes)

5. frontend/src/lib/api/:
   - Run openapi-typescript against http://localhost:8000/api/v1/openapi.json → types.ts
   - fetcher.ts: typed wrapper that injects Authorization from Supabase session
   - hooks/: useQuery/useMutation wrappers (TanStack Query) for each endpoint family

6. frontend/src/components/ui/ — ensure all shadcn components installed: button, card, input, label, form, dialog, select, tabs, table, badge, sonner, skeleton, separator, dropdown-menu, tooltip, sidebar, breadcrumb, sheet, avatar, command (for Cmd+K palette later).

7. frontend/src/app/(dashboard)/page.tsx: placeholder Dashboard showing "Welcome, {user.email}" + quick stats cards (all zeros for now).

Verification:
- pnpm lint → 0 errors
- pnpm typecheck → 0 errors
- pnpm build → successful build
- Lighthouse (chrome://lighthouse) on /login and /dashboard: Performance ≥ 90, Accessibility ≥ 95
- Manual: login with test user → redirect to /dashboard → sidebar + top bar render correctly, dark mode toggles, sign out redirects to /login

Report standard format + lighthouse scores.
```

**Manual checkpoint:**

1. Signup com email de teste → recebe magic link (verificar Supabase Auth logs no Cowork).
2. Login → chega em `/dashboard`. Sidebar colapsa com Cmd+B.
3. Theme toggle funciona (dark/light/system).
4. Tentar `/positions` sem estar logado → redirect para `/login?next=/positions`.
5. Lighthouse ≥ 90 performance, ≥ 95 accessibility.

**Duration:** 3–4 h.

---

# Phase 10 — Positions UI

**Goal:** Tela de posições com 4 abas (Physical Frames, CBOT, Basis, FX) + CRUD completo + import Excel com preview.

**Deliverables:**
- `frontend/src/app/(dashboard)/positions/page.tsx` com Tabs
- `frontend/src/app/(dashboard)/positions/frames/[id]/page.tsx` — detalhe do frame com timeline de fixações
- `frontend/src/app/(dashboard)/positions/new/page.tsx` — wizard de criação
- `frontend/src/app/(dashboard)/positions/import/page.tsx` — upload + preview + commit
- Componentes: PositionTable, FixationTimeline, FixationForm, ImportPreview

**Prompt for Claude Code:**

```
Goal: Positions management UI. Must be fast, keyboard-friendly, and visually clean.

UX principles:
- DataTable (shadcn/ui + @tanstack/react-table) with sorting, filtering, pagination.
- Create forms in Dialog (modal), not separate pages, except for Import which has its own page.
- Inline edit for notes/status where possible.
- Optimistic updates (TanStack Query) for delete/status change; rollback on error.
- Empty state with illustration (use lucide-react icons) and CTA.
- Column visibility toggle.
- Export to CSV button (client-side from current filtered rows).
- Cmd+K palette with quick actions: "Create physical frame", "Import positions", "Go to risk".

Read first:
- Component patterns in shadcn/ui docs (table, form, dialog)

Tasks:

1. frontend/src/app/(dashboard)/positions/page.tsx:
   - Tabs: Physical (frames), CBOT, Basis, FX
   - Each tab renders a DataTable with relevant columns
   - Buttons: "New position" (opens Dialog wizard), "Import", "Export CSV"

2. DataTable columns per tab:
   - Physical: counterparty, commodity, side, qty, delivery range, status, legs fixed (3 mini-bars), actions
   - CBOT: instrument, commodity, contract, side, qty (contracts), trade_date, maturity, status, unrealized P&L
   - Basis: commodity, side, qty (tons), trade_date, delivery, basis_price, status, unrealized P&L
   - FX: instrument, side, notional USD, trade_date, maturity, trade_rate, status, unrealized P&L

3. frontend/src/app/(dashboard)/positions/frames/[id]/page.tsx:
   - Header: frame metadata + status badge
   - ExposureBreakdown card: 3 progress bars (CBOT / basis / FX) showing locked vs open tons
   - FixationTimeline: vertical timeline of fixations (date, mode, qty, prices locked)
   - Actions: "Add fixation" (opens dialog with fixation_mode radio → conditional fields), "Edit frame", "Archive"

4. FixationForm:
   - Radio: fixation_mode (flat, cbot, cbot_basis, basis, fx)
   - Conditional fields:
     - cbot or cbot_basis or flat: cbot_fixed (USc/bu) input + reference_cbot_contract dropdown
     - basis or cbot_basis or flat: basis_fixed (USD/bu)
     - fx or flat: fx_fixed (BRL/USD)
   - Validation: zod schema mirrors backend; reject if total locked per leg would exceed frame qty (show remaining capacity inline).
   - Submit → POST → invalidate frame query → toast success

5. ImportPreview page:
   - Dropzone → uploads to /imports/preview
   - Renders a table of parsed rows with inline errors (red background on invalid rows, tooltip with message)
   - Footer: "X valid, Y invalid. [Fix errors] [Commit Y valid rows]"
   - On commit: POST /imports/commit, redirect to /positions with toast

6. Cmd+K palette: components/ui/command.tsx, register global via CommandProvider, hotkey cmd+k.

7. Tests (Playwright):
   - e2e_create_physical_frame: login → positions → new → fill form → submit → new row visible in list
   - e2e_add_fixation: open frame → add fixation cbot 300/1000 → progress bar updates
   - e2e_over_lock_rejected: attempt to add fixation > remaining → form shows error, no API call

Verification:
- pnpm typecheck → 0 errors
- pnpm lint → 0 errors
- pnpm test:e2e → all pass
- Lighthouse ≥ 90 / 95 on /positions
- Bundle size check: pnpm build, ensure /positions route chunk < 300 KB gzip

Report standard format + bundle sizes.
```

**Manual checkpoint:**

1. `/positions` renderiza as 4 abas com dados de teste; DataTable responsiva; dark/light funciona.
2. Criar um frame via wizard → aparece na tabela imediatamente (optimistic).
3. Abrir frame detail → adicionar 2 fixações parciais → progress bars atualizam; status do frame muda para `partial`.
4. Import do `example_import.xlsx` → preview mostra rows; commit insere tudo.
5. Cmd+K abre palette → "Create physical frame" funciona.

**Duration:** 5–6 h.

---

# Phase 11 — Risk Dashboard

**Goal:** Dashboard de risco com 7 widgets principais + drill-downs.

**Deliverables:**
- `frontend/src/app/(dashboard)/page.tsx` (overview)
- `frontend/src/app/(dashboard)/risk/page.tsx` (deep-dive)
- Widgets: MTMCard, ExposureWaterfall, VaRCard, CVaRCard, StressPanel, TimeSeriesChart, ConcentrationPie, VaRAttributionTable, MCFanChart, CorrelationHeatmap

**Prompt for Claude Code:**

```
Goal: risk dashboard — clean, dense, professional. This is the portfolio hero page.

Design principles:
- Two-column grid on desktop (split 60/40 or 50/50 as content dictates). Stack on mobile.
- Every chart: title + subtitle + "i" tooltip explaining methodology + last updated timestamp.
- Number formatting: BRL with thousand separators (1.234.567,89), USD with 2 decimals, percent with 2 decimals.
- Color palette: consistent semantic colors (green for profit, red for loss, amber for warning). Use CSS variables.
- Use Recharts consistently.

Read first:
- CLAUDE.md (Risk Metrics)
- .claude/skills/risk-engine-patterns/SKILL.md

Tasks:

1. frontend/src/app/(dashboard)/page.tsx — overview:
   - Row 1: 4 KPI cards (Total MTM BRL, Open Positions count, Net CBOT Delta, Net FX Delta)
   - Row 2: ExposureWaterfall (shadcn/ui BarChart): bars for CBOT_soja, CBOT_milho, basis_soja, basis_milho, fx, with + for long and - for short, BRL values
   - Row 3: TimeSeriesChart — MTM over the last 30 days (line), with hover tooltip
   - Row 4: 2-column: ConcentrationPie (by commodity, by instrument type) and VaR summary card (method toggle: historical/parametric/MC)

2. frontend/src/app/(dashboard)/risk/page.tsx — deep-dive:
   - Method switcher (historical / parametric / MC) + confidence slider (90/95/97.5/99) + horizon (1/5/10 days)
   - VaRCard + CVaRCard showing flat + per-leg breakdown (3 sub-values)
   - MCFanChart: path simulation visualized as filled area between p5–p95 with median line
   - StressPanel: 4 historical scenarios as cards + "Custom scenario" button opening a drawer
   - VaRAttributionTable: positions ranked by contribution, bar inline showing share_pct
   - CorrelationHeatmap: 5×5 matrix (Recharts or custom d3-like) with cell colors red→green

3. Number/date formatters in frontend/src/lib/formatters/:
   - formatBRL(value)
   - formatUSD(value)
   - formatPercent(value, decimals=2)
   - formatUScBu(value, decimals=2)
   - formatTons(value, decimals=2)
   - All use Intl.NumberFormat with pt-BR locale

4. All widgets read from TanStack Query hooks calling backend /risk/* endpoints.
   - Stale time: 60s (prices don't change faster than cron anyway).
   - Refetch on window focus.
   - Show Skeleton while loading; ErrorBoundary with retry button on error.

5. PDF export:
   - Button "Export report" on /risk page → calls a new endpoint /reports/risk-pdf that returns a PDF with all widgets rendered via puppeteer or react-pdf
   - Backend: backend/app/api/v1/reports.py using reportlab or weasyprint
   - Include: date, portfolio summary, VaR table, stress table, exposure chart, attribution top 10

6. Tests (Playwright):
   - e2e_dashboard_loads: all widgets render (skeleton → content)
   - e2e_method_switch: changing VaR method updates the number
   - e2e_pdf_export: click export → file downloads, non-empty

Verification:
- pnpm typecheck → clean
- pnpm lint → clean
- pnpm build → chunks for /dashboard and /risk < 400 KB gzip each
- Lighthouse: /dashboard perf ≥ 90, a11y ≥ 95
- Manual: load /risk, switch methods, verify numbers update coherently

Report standard format + lighthouse + bundle sizes.
```

**Manual checkpoint:**

1. `/dashboard` carrega < 1s (após cold fetch); widgets todos aparecem.
2. `/risk` → mudar método de historical para MC → valores atualizam; seed garante reprodutibilidade visível.
3. Stress panel → abrir custom scenario drawer → ajustar sliders → preview em tempo real.
4. Correlation heatmap: diagonal vermelha (1.0), off-diagonal variável.
5. Export PDF → arquivo baixa, abre, tem todas as seções.
6. Responsivo: redimensionar browser para 768px → grid colapsa corretamente.

**Duration:** 5–6 h.

---

# Phase 12 — Scenario builder + insights (polish)

**Goal:** Permitir usuário criar/salvar scenarios custom, rodar sensitivity analysis, ver P&L attribution em detalhe.

**Deliverables:**
- `frontend/src/app/(dashboard)/scenarios/page.tsx` — lista + CRUD
- `frontend/src/app/(dashboard)/scenarios/[id]/page.tsx` — editor + preview impact
- SensitivitySliders component — "what if CBOT -10%? fx +5%?" em tempo real sobre o portfolio atual

**Prompt for Claude Code:** (padrão)

**Manual checkpoint:**

1. Criar scenario "Custom test" com CBOT soja -15%, FX +10% → salva.
2. Reabrir → preview do P&L impact coerente com as fórmulas.
3. Apertar "Apply" em Risk page → stress reaplica.
4. Sensitivity slider move CBOT de -20% a +20% em tempo real, P&L atualiza com ≤100ms debounce.

**Duration:** 3–4 h.

---

# Phase 13 — Deploy + observability

**Goal:** MVP em produção: Vercel (frontend) + Render (backend) + Supabase (prod). Structured logging + error tracking + CI bloqueando merges quebrados.

**Deliverables:**
- Projeto prod no Supabase (separado do dev)
- Deploy Vercel conectado ao main
- Deploy Render conectado ao main
- Sentry (ou Logtail) integrado em FE + BE
- `.github/workflows/ci.yml` finalizado (lint + test + build + block on fail)
- `docs/DEPLOY.md` runbook

**Prompt dividido entre Claude Code (CI, Sentry integration, docs) e Cowork (Supabase prod + Vercel + Render):**

Cowork prompt:

```
Use Supabase MCP:
1. create_project "market-risk-platform-prod" em sa-east-1
2. Aplicar as 3 migrations (reuse SQL de Phase 2)
3. get_advisors security + performance → fix if any issue
4. get_publishable_keys + DATABASE_URL

Use Vercel MCP:
1. Criar projeto conectado ao repo (frontend/ diretório)
2. Set env vars: NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY, NEXT_PUBLIC_API_URL
3. deploy_to_vercel
4. get_deployment_build_logs se falhar

Backend no Render: usuário precisa fazer manual (MCP do Render não disponível). Instruções em docs/DEPLOY.md.
```

Claude Code prompt:

```
Goal: harden for production.

1. backend/app/core/logging.py: structlog com processors (add_timestamp, format_exc_info, JSONRenderer). Contextvars em cada request (request_id, user_id).
2. Sentry SDK em backend (FastAPI integration) + frontend (Next.js integration). ENV-gated: só ativa em production.
3. docs/DEPLOY.md: passo-a-passo para Render (create web service, env vars, health check path, auto-deploy from main).
4. .github/workflows/ci.yml finalizado: require branch protection, all checks must pass (lint + type + test + build).
5. backend/app/middleware/rate_limit.py: per-user rate limit (slowapi) em endpoints de risk (max 60/min).
6. CORS: prod permite apenas o domínio Vercel.
7. backend/app/api/v1/health.py: /health agora checa DB connection; /ready checa DB + externals.

Verification:
- uv run pytest → all pass
- Deploy preview URL Vercel → check /dashboard loads
- Render deploy → /health returns 200
- Sentry DSN: trigger a fake error, confirm evento chegou no dashboard Sentry

Report standard format.
```

**Manual checkpoint:**

1. Abrir URL Vercel prod → login com usuário real → dashboard funciona.
2. Render URL `/api/v1/health` → 200 OK, JSON com version.
3. Forçar erro (ex: bad JWT) → aparece em Sentry < 60s.
4. GitHub PR com `pytest` quebrado → CI vermelho, não dá para mergear.
5. GitHub Actions price_update.yml rodou à noite (checar Actions tab no dia seguinte).

**Duration:** 3–4 h.

---

# Meta — how to use this plan

## Running a phase

1. Abra Claude Code no terminal do VSCode com o repo aberto.
2. Copie o "Prompt for Claude Code" da fase atual e cole no Claude Code.
3. Claude Code vai ler os skills e executar. Se parar pra pergunta, responda.
4. Ao final, Claude Code entrega o "Report" no formato pedido. Leia.
5. Rode você mesmo o "Manual checkpoint". **Não avance se algo falhou.**
6. Commit + push. Próxima fase.

## Divisão por ambiente

| Fase | Claude Code (VSCode) | Cowork (chat aqui) |
|------|----------------------|---------------------|
| 0 | — | ADRs + CLAUDE.md edit |
| 1 | scaffold do repo | criar Supabase dev |
| 2 | ORM + schemas | aplicar migrations + RLS via Supabase MCP |
| 3 | código puro | — |
| 4 | ingestion + DAG | validar workflow cron |
| 5 | endpoints | — |
| 6 | risk core | — |
| 7 | MC + correlação | — |
| 8 | options (opcional) | — |
| 9 | FE scaffold | — |
| 10 | FE positions | — |
| 11 | FE dashboard | — |
| 12 | FE scenarios | — |
| 13 | CI + logging + docs | Supabase prod + Vercel deploy via MCP |

## Como lidar com blockers

- **Claude Code entrou em loop ou produziu código estranho:** pare, leia o `Report`, faça uma pergunta específica nova (não repita o prompt inteiro).
- **Teste falhou sem razão clara:** use a skill `engineering:debug` no Cowork aqui, passando o stack trace.
- **Decisão de arquitetura no meio do caminho:** pare, abra um ADR novo em `docs/adr/`, só depois implemente.
- **Dúvida sobre fórmula financeira:** a skill `commodity-price-decomposition` carrega automaticamente — se o Claude Code não chamou, force com "Use skill commodity-price-decomposition for this".

## Cadência sugerida (weekend warrior)

- **Sprint 1 (weekend 1 — ~8h):** P0, P1, P2 → DB pronto, repo rodando.
- **Sprint 2 (weekend 2 — ~8h):** P3, P4, P5 → backend funcional com posições e preços.
- **Sprint 3 (weekend 3 — ~8h):** P6, P7 → risk engine completo.
- **Sprint 4 (weekend 4 — ~8h):** P9, P10 → frontend com posições.
- **Sprint 5 (weekend 5 — ~8h):** P11 → dashboard de risco.
- **Sprint 6 (weekend 6 — ~6h):** P12, P13 → polish + deploy.
- **Opcional (sprint 7):** P8 options pricing.

MVP publicável ao final do Sprint 6 (≈6 weekends, ~46h).

## Quando parar para refatorar

Se no final de um sprint você sentir:
- O código está bom o suficiente pro escopo da fase.
- Os testes estão verdes.
- O checkpoint passou.

**Siga em frente.** Refactor vem depois do MVP, quando você conhecer os pain points reais.
