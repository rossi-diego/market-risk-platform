# ADR-0002: Physical contract model — Frame + Fixações (parent–child)

**Status:** Accepted
**Date:** 2026-04-16
**Deciders:** Diego Rossi (owner)

## Context

Physical soja/milho contracts in the Brazilian agribusiness are rarely struck at a single "flat" price at the moment of the trade. The dominant workflow is:

1. A **frame** is opened between buyer and seller: total tonnage, delivery window (start–end), commodity, and counterparty. At frame opening, no price is fixed yet.
2. Over the weeks or months until delivery, the party responsible for pricing (typically the one with pricing optionality — often the producer on a "to-arrive" contract) registers **fixações** (partial fixings) that lock one or more of the three price legs on a subset of the tonnage:
   - **`flat`** — locks CBOT + basis + FX simultaneously on the fixed tonnage (equivalent to "a preço fixo" for that slice).
   - **`cbot`** — locks only the CBOT leg ("fixação de bolsa"); basis and FX remain floating.
   - **`cbot_basis`** — locks CBOT and basis together ("fixou bolsa e prêmio"); FX remains floating.
   - **`basis`** — locks only the basis/prêmio; CBOT and FX remain floating.
   - **`fx`** — locks only the dollar; CBOT and basis remain floating.
3. At delivery, the physical tonnage is transferred and P&L settles based on whatever is still floating at that moment (plus any spot pricing for the residual non-fixed tonnage).

This means at any point in a frame's life, the **open exposure per leg** is a function of the frame total minus the cumulative tonnage fixed on that specific leg — different per leg. A 1000-ton frame might have 700 tons open on CBOT (because 300 were fixed via `cbot_basis`) and 500 tons open on FX (because 500 were fixed via `fx`) simultaneously.

Risk computation must operate on these **open per-leg exposures**, not on the nominal frame tonnage. Getting this wrong silently over-states or under-states hedging needs.

The original `CLAUDE.md` spec had a flat `Position` table with `cbot_at_trade`, `fx_at_trade`, `premium_at_trade` as scalar fields — adequate only for the degenerate case where all three legs were locked at the same instant (equivalent to `flat` fixation on 100% of the tonnage). It cannot represent the multi-fixation reality.

## Decision

Model the physical contract as a two-level parent–child hierarchy:

- **`physical_frames`** — the parent contract. Holds invariant properties: commodity, side, total quantity_tons, delivery_start, delivery_end, counterparty, status.
- **`physical_fixations`** — child records. Each row locks 1, 2, or 3 legs on a subset of the frame's tonnage, at a specific fixation_date, with the price(s) locked stored in `cbot_fixed`, `basis_fixed`, `fx_fixed` (nullable — only the locked legs have values).

A CHECK constraint at the DB level enforces which columns must be non-null per `fixation_mode`:

| fixation_mode | cbot_fixed | basis_fixed | fx_fixed |
|---------------|:----------:|:-----------:|:--------:|
| `flat`        | required   | required    | required |
| `cbot`        | required   | NULL        | NULL     |
| `cbot_basis`  | required   | required    | NULL     |
| `basis`       | NULL       | required    | NULL     |
| `fx`          | NULL       | NULL        | required |

The frame's `status` (`open | partial | closed | expired`) is derived at write time from the cumulative fixations (see ADR-0003 for how open exposure feeds risk).

## Options Considered

### Option A — Frame (parent) + Fixations (children), 2-level hierarchy (chosen)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Medium — one join, application code computes per-leg rollups |
| Cost | Low |
| Scalability | High — index on `frame_id`, typical frame has <20 fixations |
| Team familiarity | High — standard parent–child pattern |
| Domain fit | Excellent — mirrors how traders think and how trading systems represent this |

**Pros:**
- Natural mapping of the domain: a frame is a contract, fixações are events against it.
- Partial fixings fall out for free — each fixation row is an immutable fact.
- Auditing is built-in: the history of fixações *is* the history of pricing decisions.
- Each fixation can carry its own metadata (reference CBOT contract, broker, notes).
- CHECK constraints enforce mode/field consistency at the DB level.

**Cons:**
- Risk computation must aggregate fixings to derive open exposure per leg (compute, not O(1) lookup).
- A single frame's risk view requires a JOIN (or an embedded view `frame_exposures_view`).
- Over-fix prevention (summing fixed tons per leg must not exceed frame.quantity_tons) is enforced in application code — a DB trigger is possible but introduces lock contention.

### Option B — One position per event (flat structure, no parent)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Low DDL, high application logic |
| Cost | Low |
| Scalability | Medium — queries across "same contract" need a synthetic `frame_id` field or string matching |
| Team familiarity | High |
| Domain fit | Poor — loses the notion of "contract" |

**Pros:**
- Flat table, no joins.
- Each row is self-describing.

**Cons:**
- Loses the contract-as-unit-of-accounting abstraction — no natural place to store counterparty, delivery window, or total tonnage.
- User must manually track "which fixações belong to which frame" — error-prone, not how the business works.
- Impossible to express "open frame with 0 fixações yet" — every row needs a price.
- Status tracking on "the contract" has no target row.
- Frame-level counterparty lookups require aggregation heuristics.

### Option C — Frame + Fixations + Delivery events (3-level hierarchy)

| Dimension | Assessment |
|-----------|------------|
| Complexity | High — 3 tables, more joins, more write paths |
| Cost | Low |
| Scalability | High |
| Team familiarity | Medium |
| Domain fit | Excellent for end-to-end lifecycle including physical settlement |

**Pros:**
- Captures the full lifecycle including physical delivery/settlement and residual spot pricing.
- Natural place for logistics data (load dates, transport docs, quality adjustments).

**Cons:**
- MVP doesn't need delivery-event granularity — the `status` column + `trade_events` log (from ADR-0001) covers "what happened" sufficiently.
- Adds write complexity to every path that touches a frame.
- The platform is for market risk analysis, not operational logistics — the third level serves a different audience (ops/finance, not risk).
- Easy to add later if the use case emerges (migration additive, no schema break).

## Trade-off Analysis

The core trade-off is **how much of the real-world contract lifecycle to encode now**.

Option B is rejected because it loses the contract abstraction, and the contract is the natural unit of position management in the UI, P&L reporting, and risk aggregation.

Option C is rejected for MVP scope but is explicitly *additive* later — if the platform grows into physical operations, delivery events become a third level attached to `physical_frames`. ADR-0001's `trade_events` table partially absorbs the use case in the interim (logs `open`, `fill`, `close`, `expire` per frame).

Option A hits the sweet spot: faithful to the domain, bounded complexity, clear invariants, and extendable toward C without rewriting.

## Consequences

**What becomes easier:**
- Risk engine reads `physical_frames` + `physical_fixations` and computes per-leg open exposure with straightforward `GROUP BY frame_id, fixation_mode` logic.
- UI presents a frame-detail page with a clear fixation timeline — directly mirrors the parent–child model.
- Adding a new fixation mode later is a migration on the enum + a CHECK clause, no structural change.
- Audit trail of pricing decisions is the `physical_fixations` table itself, sorted by `fixation_date`.

**What becomes harder:**
- Over-fix prevention (sum of locked tons on a leg must not exceed frame total) is an application-level invariant. Two options:
  1. Application-layer check in the POST handler (chosen for MVP — simple, no lock contention, tolerates eventual consistency in single-writer per-frame workflows).
  2. DB trigger with SERIALIZABLE isolation — adds lock contention and complexity; deferred unless we observe races.
- "Closed" status requires computing cumulative fixations across all 3 legs — a recompute on every fixation write. Solution: `app/services/status_recompute.py` called in the same transaction as fixation create/delete.
- Reporting flat-price equivalent price of a frame needs a weighted average across all fixations — not a scalar field on the frame.

**What we'll need to revisit:**
- If traders start needing delivery/settlement granularity, promote to Option C.
- If over-fix races become real (multi-writer on same frame), introduce a DB trigger or advisory lock.
- If fixation modes expand (e.g., `cbot_fx` — lock CBOT and FX without basis), add to the enum and CHECK; no structural change.

## Action Items

1. [x] Phase 2: migrate `physical_frames` and `physical_fixations` with CHECK constraint for fixation_mode consistency.
2. [x] Phase 3: implement `app/risk/exposure.py:open_exposure_frame(frame, fixations) -> LegExposure` as the canonical function for per-leg open exposure.
3. [x] Phase 3: implement `app/services/status_recompute.py` to derive frame.status from fixations inside the same transaction.
4. [x] Phase 5: POST `/physical/frames/{id}/fixations` validates over-fix per leg before insert, returns 409 Conflict with `{"leg": "cbot", "remaining_tons": 700}` on violation.
5. [x] Phase 10: frame detail UI shows fixation timeline + per-leg progress bars (locked vs. open tons).
6. [ ] Phase 6+: document in `docs/RISK_METHODOLOGY.md` that flat-price reporting on a partially-fixed frame is a weighted average of fixation prices plus current market for unfixed legs.
