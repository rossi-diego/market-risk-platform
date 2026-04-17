-- =====================================================================
-- Migration 1/3 — Instruments schema (enums + 10 tables + CHECK constraints)
-- Phase 2 of market-risk-platform
-- =====================================================================
-- Creates:
--   - 9 enums
--   - 10 tables (prices, physical_frames, physical_fixations, 3 derivative
--     families, trade_events, mtm_premiums, scenarios, scenarios_templates)
--   - Indexes on hot access paths
--   - CHECK constraint on physical_fixations enforcing fixation_mode ↔ legs

begin;

-- Required extensions
create extension if not exists pgcrypto;

-- =====================================================================
-- Enums
-- =====================================================================

create type commodity as enum ('soja', 'milho');
create type side as enum ('buy', 'sell');
create type position_status as enum ('open', 'partial', 'closed', 'expired');
create type fixation_mode as enum ('flat', 'cbot', 'cbot_basis', 'basis', 'fx');
create type cbot_instrument as enum ('future', 'swap', 'european_option', 'american_option', 'barrier_option');
create type fx_instrument as enum ('ndf', 'swap', 'european_option', 'american_option', 'barrier_option');
create type option_type as enum ('call', 'put');
create type barrier_type as enum ('up_and_in', 'up_and_out', 'down_and_in', 'down_and_out');
create type price_source as enum ('YFINANCE_CBOT', 'YFINANCE_FX', 'B3_OFFICIAL', 'USER_MANUAL', 'CBOT_PROXY_YFINANCE');

-- =====================================================================
-- prices — time series of CBOT, FX, and basis observations
-- Public-readable by authenticated users; no user_id (shared market data)
-- =====================================================================

create table prices (
    id uuid primary key default gen_random_uuid(),
    observed_at timestamptz not null,
    instrument text not null,
    commodity commodity,
    value numeric(18, 6) not null,
    unit text not null,
    price_source price_source not null,
    created_at timestamptz not null default now(),
    constraint prices_unique_obs unique (observed_at, instrument)
);

create index prices_instrument_observed_idx on prices (instrument, observed_at desc);
create index prices_commodity_observed_idx on prices (commodity, observed_at desc) where commodity is not null;

-- =====================================================================
-- physical_frames — parent physical contract (total tonnage + delivery window)
-- =====================================================================

create table physical_frames (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    commodity commodity not null,
    side side not null,
    quantity_tons numeric(18, 4) not null check (quantity_tons > 0),
    delivery_start date not null,
    delivery_end date not null,
    counterparty text,
    status position_status not null default 'open',
    notes text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint physical_frames_delivery_window check (delivery_end >= delivery_start)
);

create index physical_frames_user_status_idx on physical_frames (user_id, status);
create index physical_frames_user_commodity_idx on physical_frames (user_id, commodity);

-- =====================================================================
-- physical_fixations — partial pricing events locking one or more legs
-- CHECK constraint enforces mode ↔ leg consistency (ADR-0002)
-- =====================================================================

create table physical_fixations (
    id uuid primary key default gen_random_uuid(),
    frame_id uuid not null references physical_frames(id) on delete cascade,
    fixation_mode fixation_mode not null,
    quantity_tons numeric(18, 4) not null check (quantity_tons > 0),
    fixation_date date not null,
    cbot_fixed numeric(18, 6),       -- USc/bu; required for flat, cbot, cbot_basis
    basis_fixed numeric(18, 6),      -- USD/bu; required for flat, cbot_basis, basis
    fx_fixed numeric(18, 6),         -- BRL/USD; required for flat, fx
    reference_cbot_contract text,
    notes text,
    created_at timestamptz not null default now(),
    constraint physical_fixations_mode_legs check (
        (fixation_mode = 'flat'       and cbot_fixed is not null and basis_fixed is not null and fx_fixed is not null) or
        (fixation_mode = 'cbot'       and cbot_fixed is not null and basis_fixed is null     and fx_fixed is null) or
        (fixation_mode = 'cbot_basis' and cbot_fixed is not null and basis_fixed is not null and fx_fixed is null) or
        (fixation_mode = 'basis'      and cbot_fixed is null     and basis_fixed is not null and fx_fixed is null) or
        (fixation_mode = 'fx'         and cbot_fixed is null     and basis_fixed is null     and fx_fixed is not null)
    )
);

create index physical_fixations_frame_idx on physical_fixations (frame_id);
create index physical_fixations_date_idx on physical_fixations (fixation_date desc);

-- =====================================================================
-- cbot_derivatives — CBOT futures, swaps, and options (ZS=F, ZC=F, ...)
-- Option fields (option_type, strike) required iff instrument is an option
-- Barrier fields required iff instrument is barrier_option
-- =====================================================================

create table cbot_derivatives (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    commodity commodity not null,
    instrument cbot_instrument not null,
    side side not null,
    contract text not null,
    quantity_contracts numeric(18, 4) not null check (quantity_contracts > 0),
    trade_date date not null,
    trade_price numeric(18, 6) not null,
    maturity_date date not null,
    option_type option_type,
    strike numeric(18, 6),
    barrier_type barrier_type,
    barrier_level numeric(18, 6),
    rebate numeric(18, 6),
    status position_status not null default 'open',
    counterparty text,
    notes text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint cbot_option_fields check (
        (instrument in ('future', 'swap')
            and option_type is null and strike is null
            and barrier_type is null and barrier_level is null)
        or
        (instrument in ('european_option', 'american_option')
            and option_type is not null and strike is not null
            and barrier_type is null and barrier_level is null)
        or
        (instrument = 'barrier_option'
            and option_type is not null and strike is not null
            and barrier_type is not null and barrier_level is not null)
    )
);

create index cbot_derivatives_user_status_idx on cbot_derivatives (user_id, status);
create index cbot_derivatives_user_maturity_idx on cbot_derivatives (user_id, maturity_date);

-- =====================================================================
-- basis_forwards — OTC contracts locking only the basis leg
-- =====================================================================

create table basis_forwards (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    commodity commodity not null,
    side side not null,
    quantity_tons numeric(18, 4) not null check (quantity_tons > 0),
    trade_date date not null,
    basis_price numeric(18, 6) not null,
    delivery_date date not null,
    reference_cbot_contract text not null,
    status position_status not null default 'open',
    counterparty text,
    notes text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index basis_forwards_user_status_idx on basis_forwards (user_id, status);
create index basis_forwards_user_delivery_idx on basis_forwards (user_id, delivery_date);

-- =====================================================================
-- fx_derivatives — USD/BRL NDFs, swaps, and options
-- Same option/barrier field constraints as cbot_derivatives
-- =====================================================================

create table fx_derivatives (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    instrument fx_instrument not null,
    side side not null,
    notional_usd numeric(18, 2) not null check (notional_usd > 0),
    trade_date date not null,
    trade_rate numeric(18, 6) not null,
    maturity_date date not null,
    option_type option_type,
    strike numeric(18, 6),
    barrier_type barrier_type,
    barrier_level numeric(18, 6),
    rebate numeric(18, 6),
    status position_status not null default 'open',
    counterparty text,
    notes text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint fx_option_fields check (
        (instrument in ('ndf', 'swap')
            and option_type is null and strike is null
            and barrier_type is null and barrier_level is null)
        or
        (instrument in ('european_option', 'american_option')
            and option_type is not null and strike is not null
            and barrier_type is null and barrier_level is null)
        or
        (instrument = 'barrier_option'
            and option_type is not null and strike is not null
            and barrier_type is not null and barrier_level is not null)
    )
);

create index fx_derivatives_user_status_idx on fx_derivatives (user_id, status);
create index fx_derivatives_user_maturity_idx on fx_derivatives (user_id, maturity_date);

-- =====================================================================
-- trade_events — polymorphic audit log across all 4 instrument families
-- No hard FK (polymorphic); application code is the sole writer
-- =====================================================================

create table trade_events (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    event_type text not null check (event_type in ('open', 'fill', 'partial_close', 'close', 'expire', 'adjust')),
    instrument_table text not null check (instrument_table in ('physical_frames', 'cbot_derivatives', 'basis_forwards', 'fx_derivatives')),
    instrument_id uuid not null,
    quantity numeric(18, 4),
    price numeric(18, 6),
    event_date timestamptz not null default now(),
    payload jsonb,
    created_at timestamptz not null default now()
);

create index trade_events_instrument_idx on trade_events (instrument_table, instrument_id, event_date desc);
create index trade_events_user_date_idx on trade_events (user_id, event_date desc);

-- =====================================================================
-- mtm_premiums — global MTM basis per commodity, editable via UI
-- Public (no user_id); single row per commodity
-- =====================================================================

create table mtm_premiums (
    commodity commodity primary key,
    premium_usd_bu numeric(18, 6) not null,
    updated_at timestamptz not null default now(),
    updated_by uuid references auth.users(id) on delete set null
);

-- Seed defaults: basis 0.50 USD/bu for both (user will edit in Settings)
insert into mtm_premiums (commodity, premium_usd_bu) values
    ('soja', 0.50),
    ('milho', 0.30);

-- =====================================================================
-- scenarios_templates — built-in historical stress scenarios (public)
-- =====================================================================

create table scenarios_templates (
    id uuid primary key default gen_random_uuid(),
    name text not null unique,
    description text,
    cbot_soja_shock_pct numeric(6, 4) not null default 0,
    cbot_milho_shock_pct numeric(6, 4) not null default 0,
    basis_soja_shock_pct numeric(6, 4) not null default 0,
    basis_milho_shock_pct numeric(6, 4) not null default 0,
    fx_shock_pct numeric(6, 4) not null default 0,
    source_period text,
    created_at timestamptz not null default now()
);

-- =====================================================================
-- scenarios — user-defined custom stress scenarios
-- =====================================================================

create table scenarios (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    name text not null,
    description text,
    cbot_soja_shock_pct numeric(6, 4) not null default 0,
    cbot_milho_shock_pct numeric(6, 4) not null default 0,
    basis_soja_shock_pct numeric(6, 4) not null default 0,
    basis_milho_shock_pct numeric(6, 4) not null default 0,
    fx_shock_pct numeric(6, 4) not null default 0,
    is_historical boolean not null default false,
    source_period text,
    created_at timestamptz not null default now(),
    constraint scenarios_user_name_unique unique (user_id, name)
);

create index scenarios_user_idx on scenarios (user_id);

-- =====================================================================
-- updated_at triggers (keeps timestamps fresh on UPDATE)
-- =====================================================================

create or replace function set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create trigger set_updated_at_physical_frames before update on physical_frames
    for each row execute function set_updated_at();

create trigger set_updated_at_cbot_derivatives before update on cbot_derivatives
    for each row execute function set_updated_at();

create trigger set_updated_at_basis_forwards before update on basis_forwards
    for each row execute function set_updated_at();

create trigger set_updated_at_fx_derivatives before update on fx_derivatives
    for each row execute function set_updated_at();

create trigger set_updated_at_mtm_premiums before update on mtm_premiums
    for each row execute function set_updated_at();

commit;
