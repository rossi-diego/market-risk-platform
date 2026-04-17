# Database Schema Reference

## Purpose

Canonical Supabase/PostgreSQL schema for the commodity-risk-dashboard.
Use this when writing migrations, Pydantic schemas, SQLAlchemy models,
or any Supabase query. All tables have RLS enabled.

---

## Tables

### `prices`

Stores daily close prices for all feeds (CBOT soja, CBOT milho proxy, FX).

```sql
CREATE TABLE prices (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker      TEXT NOT NULL,                    -- 'ZS=F', 'ZC=F', 'USDBRL=X'
    feed_name   TEXT NOT NULL,                    -- 'soja_cbot', 'milho_cbot', 'fx_usdbrl'
    price_date  DATE NOT NULL,
    close_price NUMERIC(18, 6) NOT NULL,
    price_source TEXT NOT NULL,                   -- PriceSource enum value
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now(),

    UNIQUE (ticker, price_date)
);

CREATE INDEX idx_prices_feed_date ON prices (feed_name, price_date DESC);
```

### `positions`

User's commodity purchase positions.

```sql
CREATE TABLE positions (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id               UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    commodity             TEXT NOT NULL CHECK (commodity IN ('soja', 'milho')),
    quantity_tons         NUMERIC(18, 3) NOT NULL CHECK (quantity_tons > 0),
    trade_price_brl_ton   NUMERIC(18, 4) NOT NULL,
    trade_date            DATE NOT NULL,
    contract_type         TEXT NOT NULL CHECK (contract_type IN ('spot', 'forward')),
    cbot_at_trade         NUMERIC(18, 4) NOT NULL,   -- USc/bu
    fx_at_trade           NUMERIC(18, 6) NOT NULL,   -- BRL/USD
    premium_at_trade      NUMERIC(10, 4) NOT NULL,   -- USD/bu
    counterparty          TEXT,
    price_source          TEXT NOT NULL DEFAULT 'USER_MANUAL',
    notes                 TEXT,
    import_batch_id       UUID REFERENCES import_batches(id),
    created_at            TIMESTAMPTZ DEFAULT now(),
    updated_at            TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE positions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users see own positions" ON positions
    FOR ALL USING (auth.uid() = user_id);

CREATE INDEX idx_positions_user_commodity ON positions (user_id, commodity, trade_date DESC);
```

### `mtm_config`

Global MTM premium configuration per commodity (one row per commodity per user).

```sql
CREATE TABLE mtm_config (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    commodity       TEXT NOT NULL CHECK (commodity IN ('soja', 'milho')),
    mtm_premium_usd_bu NUMERIC(10, 4) NOT NULL DEFAULT 0,
    updated_at      TIMESTAMPTZ DEFAULT now(),

    UNIQUE (user_id, commodity)
);

ALTER TABLE mtm_config ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users see own config" ON mtm_config
    FOR ALL USING (auth.uid() = user_id);
```

### `stress_scenarios`

User-defined hypothetical stress scenarios (historical ones are hard-coded in the backend).

```sql
CREATE TABLE stress_scenarios (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name              TEXT NOT NULL,
    soja_shock_pct    NUMERIC(8, 2) NOT NULL,
    milho_shock_pct   NUMERIC(8, 2) NOT NULL,
    fx_shock_pct      NUMERIC(8, 2) NOT NULL,
    description       TEXT,
    is_active         BOOLEAN DEFAULT true,
    created_at        TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE stress_scenarios ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users see own scenarios" ON stress_scenarios
    FOR ALL USING (auth.uid() = user_id);
```

### `import_batches`

Audit trail for Excel/CSV uploads.

```sql
CREATE TABLE import_batches (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    filename      TEXT NOT NULL,
    storage_path  TEXT NOT NULL,     -- Supabase Storage path
    rows_imported INT NOT NULL DEFAULT 0,
    rows_skipped  INT NOT NULL DEFAULT 0,
    errors        JSONB,             -- array of row-level error objects
    created_at    TIMESTAMPTZ DEFAULT now()
);
```

### `risk_snapshots` (optional, for caching)

Stores computed risk metrics to avoid recalculating on every page load.

```sql
CREATE TABLE risk_snapshots (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    snapshot_date     DATE NOT NULL,
    portfolio_value_brl NUMERIC(20, 2),
    var_historical_95 NUMERIC(20, 2),
    var_historical_99 NUMERIC(20, 2),
    var_parametric_95 NUMERIC(20, 2),
    var_mc_95         NUMERIC(20, 2),
    cvar_95           NUMERIC(20, 2),
    cvar_99           NUMERIC(20, 2),
    computed_at       TIMESTAMPTZ DEFAULT now(),
    price_sources     JSONB,         -- which feeds were used + data quality flags

    UNIQUE (user_id, snapshot_date)
);
```

---

## Supabase Storage Buckets

| Bucket name        | Purpose                           | Access     |
|--------------------|-----------------------------------|------------|
| `position-imports` | Raw Excel/CSV uploads             | Private    |
| `export-reports`   | Generated PDF/Excel risk reports  | Private    |

---

## Alembic Notes

Even with Supabase, track all DDL changes through Alembic migrations.
RLS policies and custom SQL go in `migrations/sql/` and are referenced
in migration scripts via `op.execute(open("migrations/sql/file.sql").read())`.

Never use `alembic --autogenerate` for Supabase-managed tables (auth.users etc).
Only autogenerate for tables defined in the app's SQLAlchemy models.
