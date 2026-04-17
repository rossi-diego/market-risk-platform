# Supabase migrations

SQL files that define the authoritative market-risk-platform database schema, RLS policies, and seed data. These run **once** against a fresh Supabase project; afterward, the Alembic baseline (Phase 2) takes over tracking further changes.

## Files

| Order | File | What it does |
|-----:|------|--------------|
| 1 | `20260416000001_instruments_schema.sql` | 9 enums + 10 tables (`prices`, `physical_frames`, `physical_fixations`, `cbot_derivatives`, `basis_forwards`, `fx_derivatives`, `trade_events`, `mtm_premiums`, `scenarios`, `scenarios_templates`) + CHECK constraints + indexes + `updated_at` triggers. Seeds default MTM basis (0.50 USD/bu soja, 0.30 milho). |
| 2 | `20260416000002_rls_policies.sql` | Enables RLS on 7 user-scoped tables; policies use `auth.uid() = user_id`. `physical_fixations` inherits via frame. `prices`, `mtm_premiums`, `scenarios_templates` are authenticated-read. |
| 3 | `20260416000003_seed_scenario_templates.sql` | Inserts 4 built-in historical stress scenarios (2008 GFC, 2012 drought, 2020 COVID, 2022 Ukraine). Idempotent via `on conflict (name) do update`. |

Run them **in order**. Each is wrapped in `begin; ... commit;` — either the whole file applies or nothing does.

## How to apply

### Option A — Supabase Studio (web UI)

1. Open the project at `https://app.supabase.com/project/<project-id>`.
2. Left sidebar → **SQL Editor**.
3. Open file 1, paste its contents, click **Run**. Wait for success message.
4. Repeat for files 2 and 3 **in order**.
5. Left sidebar → **Table Editor** → confirm all 10 tables are present and show the RLS badge (green shield) on the 7 user-scoped ones.

### Option B — Supabase CLI (advanced)

```bash
supabase link --project-ref <project-ref>
supabase db push --linked
```

(This will apply any files in `supabase/migrations/` that haven't been applied yet, tracked via `supabase_migrations.schema_migrations`.)

### Option C — Cowork MCP (fastest, preferred when available)

Ask the Cowork assistant to apply each migration via `apply_migration` against the project ID. The assistant will run them in order and report back.

## Verification after applying

Run in SQL Editor to sanity-check:

```sql
-- 10 tables expected
select count(*) from pg_tables where schemaname = 'public';

-- RLS enabled on user tables
select tablename, rowsecurity
from pg_tables
where schemaname = 'public'
  and tablename in ('physical_frames','physical_fixations','cbot_derivatives','basis_forwards','fx_derivatives','trade_events','scenarios');
-- All rows should show rowsecurity = true.

-- 4 historical scenarios seeded
select name, source_period from scenarios_templates order by source_period;

-- 2 MTM basis defaults
select * from mtm_premiums;
```

## Relationship to Alembic

After these 3 migrations apply, the backend runs `alembic stamp head` (Phase 2) to mark the DB at an empty baseline revision. All **future** schema changes go through Alembic autogenerate, not raw SQL in this folder. This folder captures the single bootstrap event; Alembic captures evolution.
