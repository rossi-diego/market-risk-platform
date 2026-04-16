# ADR-0001: Four-table instrument model

**Status:** Accepted
**Date:** 2026-04-16
**Deciders:** Diego Rossi (owner)

## Context

The platform needs to track four structurally distinct families of positions:

1. **Physical contracts** — tonnage of soja/milho with delivery window, counterparty, and a variable lifecycle of partial price-fixings (covered in ADR-0002).
2. **CBOT derivatives** — exchange-traded instruments on `ZS=F` / `ZC=F` (or OTC equivalents), quoted in USc/bu, with instrument types `future | swap | european_option | american_option | barrier_option` and option-specific fields (strike, option_type, barrier_level, rebate).
3. **Basis forwards** — OTC contracts that lock only the basis leg (USD/bu on top of a specific CBOT reference), with delivery_date and reference CBOT contract.
4. **FX derivatives** — USD/BRL instruments with notional in USD, instrument types `ndf | swap | european_option | american_option | barrier_option`, and their own option fields.

These families share *some* fields (user_id, side, status, counterparty, trade_date, notes) but diverge heavily on domain-specific fields and validation rules. The price-formation model in `CLAUDE.md` further requires each family to map cleanly onto one or more legs of exposure (CBOT delta, basis delta, FX delta) so aggregated risk can be computed.

The original spec in `CLAUDE.md` modeled a single `Position` table with `contract_type: "spot" | "forward"` and premium as a field. This was sufficient for a long-only physical-only MVP but cannot represent the expanded scope (long/short, standalone derivatives, partial fixations, options).

## Decision

Model each of the four families as its own first-class relational table, with a shared convention for common fields (`side`, `status`, `user_id`, `counterparty`, timestamps, soft metadata) and family-specific columns/constraints for everything else. A separate `trade_events` table logs lifecycle transitions across all four.

Tables:

- `physical_frames` + `physical_fixations` (parent–child, see ADR-0002)
- `cbot_derivatives`
- `basis_forwards`
- `fx_derivatives`
- `trade_events` (polymorphic audit log via `instrument_table` + `instrument_id`)

## Options Considered

### Option A — Four separate tables (chosen)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Medium — 4 ORM modules, 4 CRUD endpoint sets, 4 DataTables in the UI |
| Cost | Low — storage cost is negligible; dev cost is bounded by family count (fixed at 4) |
| Scalability | High — each table indexes on its natural access patterns |
| Team familiarity | High — SQL standard, no extensions, every ORM supports it |
| Type safety | High — DB-level CHECK constraints enforce option/barrier field presence per instrument subtype |
| Query complexity | Medium — cross-family queries need `UNION ALL` or application-layer aggregation |

**Pros:**
- Database schema documents the domain: reading the DDL tells you what instruments exist.
- Constraints enforced at the strongest possible level (DB): fixation_mode consistency (ADR-0002), option field presence, barrier completeness.
- Native Postgres enums per family (e.g., `cbot_instrument` vs `fx_instrument`) prevent invalid cross-family values.
- RLS policies are straightforward: each table has its own `auth.uid() = user_id` policy.
- Type generation (`supabase gen types typescript`) produces clean, narrow types per family.
- Migration evolution per family is independent — changing a CBOT-only field doesn't churn FX rows.

**Cons:**
- Cross-family reporting (e.g., "all positions by counterparty across everything") requires a UNION view or a reporting layer.
- More boilerplate: 4 CRUD sets, 4 Pydantic families, 4 ORM files.
- The lifecycle audit log (`trade_events`) is polymorphic (`instrument_table` + `instrument_id`), which lacks FK integrity at the DB level.

### Option B — Single generic `positions` table with `instrument_type` enum + JSONB payload

| Dimension | Assessment |
|-----------|------------|
| Complexity | Low on DDL, high on validation (all constraints migrate to application layer) |
| Cost | Low |
| Scalability | Medium — GIN indexes on JSONB needed for any queryable field; harder to reason about |
| Team familiarity | Medium — JSONB querying is less ergonomic |
| Type safety | Low — DB can't enforce that a barrier_option has a barrier_level |
| Query complexity | Low for uniform queries, high for family-specific |

**Pros:**
- One table, one CRUD, one model — less code.
- Adding new instrument families means adding an enum value + handling code, no migration.
- Cross-family queries are trivial.

**Cons:**
- Schema is opaque — JSONB payload is a "here be dragons" zone.
- Validation lives entirely in Pydantic/application code; a rogue direct insert bypasses everything.
- Loses native enum per family (can't prevent `barrier_type` on an `ndf`).
- Indexing option-specific fields (for "all ITM calls expiring next week") requires GIN indexes or computed columns — more complex than plain B-tree.
- Supabase auto-generated TS types would have `payload: Json` for every row, defeating most of the typing value.

### Option C — Physical + one generic `derivative` table with `instrument_type` discriminator + nullable columns for all types

| Dimension | Assessment |
|-----------|------------|
| Complexity | Medium — 2 tables, many nullable columns |
| Cost | Low |
| Scalability | Medium |
| Team familiarity | Medium |
| Type safety | Medium — can enforce per-type CHECK constraints but they grow messy |
| Query complexity | Low for derivatives, still need UNION with physical |

**Pros:**
- Compromise between A and B — fewer tables than A, more structure than B.
- Derivative cross-family queries simpler than in A.

**Cons:**
- Every row has FX-specific fields (notional_usd) and CBOT-specific fields (contract, quantity_contracts) with most NULL — sparse table.
- CHECK constraints grow into a giant boolean expression as instruments are added.
- Unit of measure is mixed (contracts vs USD notional vs tons) in the same column or needs polymorphic columns.
- Postgres native enums would have to be merged into one super-enum, losing per-family enforcement.

## Trade-off Analysis

The core trade-off is **DB-level type safety and readability vs. boilerplate reduction**. With four stable, well-understood instrument families and a small codebase, the boilerplate of Option A is bounded and one-off. The type safety and schema documentation wins compound as the codebase grows, the team onboards new contributors, and the portfolio piece is read by reviewers who will scan the DDL to judge domain modeling.

Option B's JSONB approach is tempting for velocity but directly undermines two stated goals of this project: (1) demonstrating production-grade data engineering patterns, and (2) enabling the risk engine to trust the shape of its inputs. Option B pushes validation to runtime and makes it easy to ship bugs that a CHECK constraint would have caught at write time.

Option C has the worst of both worlds for this domain: still forces UNION for physical+derivative queries, still sparse schema, still loses family-specific enums.

## Consequences

**What becomes easier:**
- Reasoning about data: the DDL *is* the domain model.
- Enforcing invariants that matter (option fields present when instrument is an option, barrier fields present only on barrier options, fixation-mode consistency on physical fixations via ADR-0002).
- Supabase generated TS types are narrow and useful in the frontend.
- Per-family migration evolution.
- Family-specific indexes and RLS policies.

**What becomes harder:**
- Cross-family reporting needs a dedicated view (e.g., `all_positions_view`) that UNIONs the four tables and normalizes to a reporting row shape.
- `trade_events` is a polymorphic log without an FK — we accept soft referential integrity there, enforced by application writes and audit-log monotonicity.
- Adding a fifth family (e.g., options on spreads) means a new migration and code path, not a new enum value.

**What we'll need to revisit:**
- If the fifth family is added, re-evaluate whether Option C (grouping derivative families) becomes attractive.
- If cross-family reporting becomes frequent and slow, add a materialized view rebuilt on write triggers.

## Action Items

1. [x] Phase 2: create migration for the 4 instrument tables + `trade_events` + `physical_fixations`.
2. [x] Phase 2: create `all_positions_view` UNION view for reporting queries.
3. [x] Phase 3: ORM modules mirror this structure one-to-one (`app/models/physical.py`, `cbot.py`, `basis.py`, `fx.py`, `events.py`).
4. [x] Phase 5: FastAPI endpoints grouped per family (`app/api/v1/physical.py`, `cbot.py`, `basis.py`, `fx.py`).
5. [ ] Phase 2: decide whether `trade_events` gets a `CHECK (instrument_table IN (...))` guard — recommended, trivial to add.
