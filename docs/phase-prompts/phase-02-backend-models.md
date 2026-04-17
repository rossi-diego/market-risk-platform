# Phase 2 — Backend ORM + schemas + Alembic baseline

> Paste-load instructions for Claude Code: read this file end-to-end, then execute every section in order. Bypass mode is assumed active.

## Prerequisite (must be true before starting)

The Supabase dev project exists and the full schema (10 tables + 9 enums + RLS policies) is already applied. This is provisioned from Cowork via the Supabase MCP, NOT from Claude Code. If any of the tables/enums listed below are missing, STOP and return the handoff block with `Status: ❌ blocked-on-supabase`.

Tables that must exist in `public` schema:
- `prices`
- `physical_frames`
- `physical_fixations`
- `cbot_derivatives`
- `basis_forwards`
- `fx_derivatives`
- `trade_events`
- `mtm_premiums`
- `scenarios`
- `scenarios_templates`

Enums that must exist: `commodity`, `side`, `position_status`, `fixation_mode`, `cbot_instrument`, `fx_instrument`, `option_type`, `barrier_type`, `price_source`.

Verify upfront with:

```bash
cd backend
uv run python -c "
import asyncio, asyncpg, os
async def check():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'].replace('+asyncpg',''))
    tables = [r['tablename'] for r in await conn.fetch(\"select tablename from pg_tables where schemaname='public'\")]
    required = {'prices','physical_frames','physical_fixations','cbot_derivatives','basis_forwards','fx_derivatives','trade_events','mtm_premiums','scenarios','scenarios_templates'}
    missing = required - set(tables)
    print('missing:', missing) if missing else print('all 10 tables present')
    await conn.close()
asyncio.run(check())
"
```

If output is `all 10 tables present`, proceed. Otherwise STOP.

## Context

Phase 2 of the market-risk-platform build plan. Mirror the Supabase schema in SQLAlchemy 2.0 ORM models and Pydantic v2 schemas. Initialize Alembic with a baseline revision stamped to the current DB state (no autogeneration — the schema already exists).

Reference:
- `CLAUDE.md` — Instrument Schema, Fixation Modes sections.
- `docs/adr/0001-instrument-model.md`, `0002-fixacao-model.md`.
- `.claude/skills/supabase-fastapi-async/SKILL.md`.

## Running mode

`--dangerously-skip-permissions` active. After validation passes, commit and push to `main` autonomously.

## Tasks

### 1. SQLAlchemy ORM models

One file per domain family under `backend/app/models/`. Use SQLAlchemy 2.0 typed syntax: `Mapped[...]`, `mapped_column(...)`. Enum columns use `sqlalchemy.Enum(PyEnum, name="<enum_name>", native_enum=True, create_type=False)` so Postgres native enums are used without re-creation.

Files:

- `backend/app/models/__init__.py` — re-export all models for Alembic autodetect.
- `backend/app/models/base.py`:
  - `Base = DeclarativeBase`.
  - `class TimestampMixin`: `created_at`, `updated_at` as `Mapped[datetime]` with server defaults `now()` and `onupdate=now()`.
- `backend/app/models/enums.py` — Python enums mirroring DB enums (string values must match exactly):
  - `Commodity(str, Enum)`: `SOJA="soja"`, `MILHO="milho"`
  - `Side(str, Enum)`: `BUY="buy"`, `SELL="sell"`
  - `PositionStatus(str, Enum)`: `OPEN`, `PARTIAL`, `CLOSED`, `EXPIRED`
  - `FixationMode(str, Enum)`: `FLAT`, `CBOT`, `CBOT_BASIS`, `BASIS`, `FX`
  - `CBOTInstrument(str, Enum)`: `FUTURE`, `SWAP`, `EUROPEAN_OPTION`, `AMERICAN_OPTION`, `BARRIER_OPTION`
  - `FXInstrument(str, Enum)`: `NDF`, `SWAP`, `EUROPEAN_OPTION`, `AMERICAN_OPTION`, `BARRIER_OPTION`
  - `OptionType(str, Enum)`: `CALL`, `PUT`
  - `BarrierType(str, Enum)`: `UP_AND_IN`, `UP_AND_OUT`, `DOWN_AND_IN`, `DOWN_AND_OUT`
  - `PriceSource(str, Enum)`: `YFINANCE_CBOT`, `YFINANCE_FX`, `B3_OFFICIAL`, `USER_MANUAL`, `CBOT_PROXY_YFINANCE`
- `backend/app/models/prices.py` → `Price` (no user_id).
- `backend/app/models/physical.py` → `PhysicalFrame` and `PhysicalFixation` with relationship: `fixations: Mapped[list["PhysicalFixation"]]` and the inverse `frame`.
- `backend/app/models/cbot.py` → `CBOTDerivative`.
- `backend/app/models/basis.py` → `BasisForward`.
- `backend/app/models/fx.py` → `FXDerivative`.
- `backend/app/models/events.py` → `TradeEvent`.
- `backend/app/models/config.py` → `MTMPremium`, `ScenarioTemplate`, `Scenario`.

Column types must match `CLAUDE.md` exactly: `quantity_tons` is `Numeric(18, 4)`, `basis_fixed` is `Numeric(18, 6)`, etc. Use `Decimal` in Python.

### 2. Pydantic v2 schemas

Under `backend/app/schemas/`, one file per domain family. Each file exposes three variants:

- `<Name>In` — POST body (no `id`, no timestamps, no `user_id` — derived from JWT).
- `<Name>Out` — GET response (includes `id`, timestamps, `user_id`).
- `<Name>Update` — PATCH body (all fields `Optional`).

Requirements:
- Decimal fields typed as `Decimal` (NOT `float`).
- Enum fields typed as `Literal[...]` matching the DB enum string values.
- `PhysicalFixationIn` must have a `model_validator(mode="after")` that mirrors the DB CHECK constraint: for each `fixation_mode`, the right subset of `cbot_fixed | basis_fixed | fx_fixed` must be non-null. Raise with a clear error message.
- `ConfigDict(from_attributes=True)` on all `*Out` classes.

Files:
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/common.py` (shared types: `LiteralCommodity`, `LiteralSide`, etc. as TypeAliases)
- `backend/app/schemas/prices.py`
- `backend/app/schemas/physical.py` — includes both `PhysicalFrameIn/Out/Update` and `PhysicalFixationIn/Out/Update` plus `PhysicalFrameDetailOut` that nests `list[PhysicalFixationOut]`.
- `backend/app/schemas/cbot.py`
- `backend/app/schemas/basis.py`
- `backend/app/schemas/fx.py`
- `backend/app/schemas/events.py`
- `backend/app/schemas/config.py`

### 3. Alembic initialization + baseline

- `cd backend && uv run alembic init alembic` (creates `alembic/` and `alembic.ini`).
- Edit `alembic/env.py`:
  - Import `Base` from `app.models.base`.
  - Import all models via `from app.models import *` so metadata is populated.
  - Use async config: `connectable = async_engine_from_config(...)`.
  - Read DB URL from `app.core.config.settings.DATABASE_URL`, converting `postgresql+asyncpg` → `postgresql` for Alembic's synchronous runner OR use `async_migration` helper.
- Edit `alembic.ini`:
  - Set `sqlalchemy.url = ` (empty, sourced from env.py).
  - Set `script_location = alembic`.
- Create a baseline revision:
  - `uv run alembic revision -m "baseline — schema created via Supabase Studio"` generates an empty migration file.
  - Edit the generated file: leave `upgrade()` and `downgrade()` as `pass` (no-ops).
  - Add a comment at top: `# Baseline migration. Schema was provisioned outside Alembic (via Supabase Studio/MCP). Future migrations evolve from this point.`
- `uv run alembic stamp head` to mark the DB at this revision without running anything.
- `uv run alembic current` should now output the baseline revision hash.

### 4. DB smoke test script

`backend/scripts/db_smoke.py`:

- Opens an async session via `app.core.db.get_session`.
- Runs: `SELECT count(*) FROM prices`, `SELECT count(*) FROM physical_frames` (expect 0 for both on fresh DB).
- Exits 0 on success, non-zero on connection/query failure.
- Add shebang and `if __name__ == "__main__": asyncio.run(main())`.

### 5. Model unit tests

`backend/tests/unit/test_models.py`:

- Uses `pytest-asyncio` and an in-memory SQLite for pure-Python model tests (DO NOT touch real Supabase here — `native_enum=False` needed in a test-only metadata copy since SQLite has no enums).
  - Actually simpler: skip SQLite. Test models by instantiation + attribute access only, no DB roundtrip in unit tests. DB roundtrip is integration territory (Phase 5).
- Parametrized tests per model:
  - Construct with valid kwargs.
  - Verify enum coercion (passing a string matches the enum).
  - Verify `Decimal` round-trip.
- Pydantic validator tests (these DO NOT need a DB):
  - `PhysicalFixationIn` with `fixation_mode=flat` and all 3 legs set → valid.
  - `PhysicalFixationIn` with `fixation_mode=cbot` and only `cbot_fixed` set → valid.
  - `PhysicalFixationIn` with `fixation_mode=cbot` but `basis_fixed` also set → ValidationError.
  - `PhysicalFixationIn` with `fixation_mode=flat` but `fx_fixed=None` → ValidationError.
  - Parameterize all 5 modes × valid and invalid case.

## Constraints

- Do NOT run Alembic `upgrade` or `downgrade` against the remote DB beyond `stamp head`.
- Do NOT modify the Supabase schema from Claude Code. Any schema change requires a Cowork + MCP trip.
- Do NOT add files outside: `backend/app/models/`, `backend/app/schemas/`, `backend/alembic/`, `backend/scripts/`, `backend/tests/`.

## MANDATORY validation

Run in order, capture output:

1. `cd backend && uv run mypy app/ --strict`  → 0 errors
2. `cd backend && uv run ruff check .`  → clean
3. `cd backend && uv run pytest tests/unit/test_models.py -v`  → all pass
4. `cd backend && uv run alembic current`  → prints baseline revision hash (not empty)
5. `cd backend && uv run python scripts/db_smoke.py`  → exits 0, prints counts
6. `cd backend && uv run python -c "from app.models import *; from app.schemas import *; print('import ok')"`  → prints "import ok"
7. `cd backend && uv run python -c "from app.models.physical import PhysicalFrame, PhysicalFixation; print(PhysicalFrame.__tablename__, PhysicalFixation.__tablename__)"`  → prints `physical_frames physical_fixations`

Invariants:
- [ ] mypy strict: 0 errors
- [ ] All model unit tests pass (target: ≥15 tests across files)
- [ ] Alembic baseline revision created AND stamped on DB (`alembic current` == head)
- [ ] DB smoke test succeeds (connection + SELECT works)
- [ ] Each of the 10 tables has a corresponding SQLAlchemy model
- [ ] Each model family has In/Out/Update Pydantic schemas
- [ ] PhysicalFixationIn validator covers all 5 fixation modes (test matrix)

## Commit + push

```bash
git add -A
git status --short
git commit -m "feat(models): Phase 2 — SQLAlchemy ORM + Pydantic schemas + Alembic baseline

- 10 SQLAlchemy 2.0 typed models mirroring the Supabase schema (prices, 4 instrument families, events, config)
- Pydantic v2 In/Out/Update schemas with mode-aware fixation validator matching DB CHECK constraint
- Alembic initialized with baseline revision stamped at current DB state
- DB smoke script + model unit tests with 5-mode fixation validator matrix

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin main
```

## COWORK HANDOFF

```
=== COWORK HANDOFF — PHASE 2 BEGIN ===

Status: <✅ shipped / ❌ failed / ❌ blocked-on-supabase>
Mode:   --dangerously-skip-permissions
Date:   <YYYY-MM-DD HH:MM local>

Prerequisite check:
  [✓/✗] 10 required tables present in public schema: <missing list or "none">

Git state (post-commit):
  branch:       main
  local HEAD:   <sha>
  origin/main:  <sha>
  aligned:      <yes/no>
  tree clean:   <yes/no>

Commit (if shipped):
  SHA:     <sha>
  subject: feat(models): Phase 2 — SQLAlchemy ORM + Pydantic schemas + Alembic baseline
  push:    <paste the "To ... main -> main" line>

Validation matrix:
  [✓/✗] 1. mypy strict            <N source files, 0 errors | N errors>
  [✓/✗] 2. ruff check             <clean | N issues>
  [✓/✗] 3. pytest unit/test_models <N/N passed>
  [✓/✗] 4. alembic current         <revision hash or "(empty)">
  [✓/✗] 5. db_smoke                <prices=N, physical_frames=N>
  [✓/✗] 6. full import smoke       <ok | error>
  [✓/✗] 7. PhysicalFrame tablename <physical_frames physical_fixations | other>

Files created:
  backend/app/models/:    <list>
  backend/app/schemas/:   <list>
  backend/alembic/:       <list>
  backend/scripts/:       db_smoke.py
  backend/tests/unit/:    test_models.py

Blockers / errors (if ❌):
  <step number>: <last 20 lines of command output>
  hypothesis: <your best guess at cause>
  scope-of-fix: <within prompt scope / requires Diego / requires Cowork>

Next expected action (Diego):
  - Verify in Supabase Studio that RLS badges are green on all user-scoped tables.
  - Return to Cowork to validate Phase 2 and trigger Phase 3 (domain core — pricing + exposure).

Open questions for Diego:
  <list or "none">

=== COWORK HANDOFF — PHASE 2 END ===
```
