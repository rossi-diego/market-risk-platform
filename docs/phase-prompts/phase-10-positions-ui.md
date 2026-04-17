# Phase 10 — Positions UI (4 tabs + frame detail + Excel import)

> Paste-load: read this file end-to-end, execute every section. Bypass mode is assumed active.

## Context

Phase 10 is the positions management surface. It's the **most UI-heavy phase** and takes the longest (5-6 h). By the end: users can view / create / edit / delete positions across all 4 instrument families, drill into frame detail with fixation timeline, and import from Excel.

Reference:
- `CLAUDE.md` — Instrument Schema, Fixation Modes sections.
- `docs/BUILD_PLAN.md` — Phase 10 section.
- Phase 5 OpenAPI spec (`/api/v1/physical`, `/cbot`, `/basis`, `/fx`, `/imports`).

## Running mode

`--dangerously-skip-permissions` active. Commit + push to main on validation success.

## Design principles

- DataTable via `@tanstack/react-table` + shadcn Table components.
- Create forms in `Dialog` (modal), not separate pages, except for `/positions/import` which has its own page.
- Inline edit for fields like notes and status.
- Optimistic updates via TanStack Query mutations; rollback on error with toast.
- Empty states: `lucide-react` icon + CTA button.
- Column visibility toggle.
- Export current filtered rows to CSV (client-side).
- `Cmd+K` command palette for quick actions.

## Tasks

### 1. Positions index with 4 tabs

`frontend/src/app/(dashboard)/positions/page.tsx`:

- `Tabs` primitive from shadcn. Tab values: `physical`, `cbot`, `basis`, `fx`.
- Each tab mounts a DataTable component specific to that instrument family.
- Top-right action bar: `New position` (dropdown: pick family → opens Dialog), `Import`, `Export CSV`.
- URL state: active tab synced via `?tab=cbot` query param.

### 2. DataTable components

Under `frontend/src/components/positions/tables/`:

- `PhysicalFramesTable.tsx`:
  - Columns: counterparty, commodity (badge), side (badge), qty_tons, delivery range, status (badge), **3 mini progress bars** showing locked tons per leg (cbot/basis/fx), actions menu (view detail, edit, archive).
  - Row click → navigate to `/positions/frames/{id}`.
- `CbotTable.tsx`:
  - Columns: instrument (badge), commodity, contract, side, qty_contracts, trade_date, maturity, status, unrealized_pnl (derived client-side from current prices via `usePrice`), actions.
- `BasisTable.tsx`:
  - Columns: commodity, side, qty_tons, trade_date, delivery, basis_price (USD/bu), status, actions.
- `FxTable.tsx`:
  - Columns: instrument, side, notional_usd, trade_date, maturity, trade_rate, status, actions.

All tables share a common `DataTable` wrapper that provides sorting, filtering (debounced input), pagination, and column visibility.

### 3. Create position wizard

One `PositionCreateDialog` in `frontend/src/components/positions/dialogs/PositionCreateDialog.tsx`:

- Step 1: pick family (radio tiles: Physical, CBOT, Basis, FX).
- Step 2: family-specific form fields built with `react-hook-form` + `zod` (schema generated from OpenAPI types + manual refinement).
- Submit → POST via typed client → invalidate relevant list query → toast success.

For CBOT and FX options, the form must conditionally show option_type / strike / barrier_type / barrier_level based on instrument.

### 4. Frame detail

`frontend/src/app/(dashboard)/positions/frames/[id]/page.tsx`:

- Header: frame metadata (commodity, side, counterparty, delivery, status badge).
- `ExposureBreakdown` card: 3 progress bars (CBOT / basis / FX) showing `locked_tons` / `quantity_tons`, with color (green near 0, amber mid, red high).
- `FixationTimeline` component: vertical timeline of fixations sorted by `fixation_date` desc; each row shows mode, qty, prices locked, reference contract.
- Actions: `Add fixation` (opens `FixationDialog`), `Edit frame` (counterparty/notes/status only), `Archive`.

`FixationDialog`:
- Radio for `fixation_mode` (5 options).
- Conditional inputs per mode (mirror the DB CHECK constraint).
- Inline validation: reject if the new fixation would exceed remaining tons per leg.
- On 409 from backend: parse `remaining_tons` from the problem detail, show inline error.

### 5. Import page

`frontend/src/app/(dashboard)/positions/import/page.tsx`:

- Dropzone (react-dropzone) accepts `.xlsx` / `.xls`.
- Preview call: `POST /imports/preview` → render parsed rows per sheet, highlight invalid rows in red with Tooltip showing error details.
- Footer bar: "X valid, Y invalid. [Download corrected template] [Commit Y valid rows]".
- On commit: generate a UUID as `import_id` (for idempotency), `POST /imports/commit` with file + id, redirect to `/positions` with success toast on 2xx.
- Link to download `docs/example_import.xlsx` as starting template.

### 6. Cmd+K palette

`frontend/src/components/command/CommandPalette.tsx`:

- Global hotkey via `useEffect` + event listener on `document`.
- Uses shadcn's `Command` primitive inside a `CommandDialog`.
- Actions: "New physical frame", "New CBOT derivative", "New basis forward", "New FX derivative", "Import positions", "Go to dashboard", "Go to risk", "Sign out".

### 7. E2E tests (Playwright)

`frontend/e2e/positions.spec.ts` (install Playwright via `pnpm add -D @playwright/test && pnpm playwright install`):

- `create-physical-frame`: login → /positions → click "New" → pick Physical → fill form → submit → frame visible in list.
- `add-fixation`: navigate to frame detail → add 300t CBOT fixation → progress bar updates.
- `over-lock-rejected`: attempt 600t + 500t CBOT on a 1000t frame → second errors with 409, inline error visible, no DB write (confirm via backend list query not incrementing).
- `import-flow`: upload `docs/example_import.xlsx` → preview shows 12+ rows → commit → positions appear in respective tables.

## Constraints

- NO `any` types. Use generated OpenAPI types everywhere.
- DataTable filter input: debounce 250ms to avoid key-per-stroke re-renders.
- Forms: all `zod` schemas must mirror the backend Pydantic constraints.
- Dialogs: close on Escape, backdrop click.

## MANDATORY validation

1. `cd frontend && pnpm lint`  → 0 errors
2. `cd frontend && pnpm typecheck`  → 0 errors
3. `cd frontend && pnpm build`  → successful, all new routes present, chunks `/positions` route < 300 KB gzip
4. `cd frontend && pnpm playwright test e2e/positions.spec.ts`  → all pass
5. Lighthouse on `/positions`: perf ≥ 90, a11y ≥ 95
6. Manual:
   - 4 tabs render with empty state → create 1 position each family
   - Frame detail shows fixation timeline + exposure bars
   - Import `docs/example_import.xlsx` preview → commit → rows appear
   - Cmd+K opens palette, navigating works

Invariants:
- [ ] All 4 family tabs have working CRUD
- [ ] Over-fix flow: inline error + backend 409 + no DB write (DB smoke shows no extra row)
- [ ] Import flow preview + commit works end-to-end
- [ ] Cmd+K palette opens globally
- [ ] Lighthouse thresholds met on /positions

## Commit + push

```bash
git add -A
git commit -m "feat(frontend): Phase 10 — positions UI (4 family tables + frame detail + Excel import)

- /positions tabbed index with DataTable per family
- PositionCreateDialog with react-hook-form + zod (conditional option/barrier fields)
- /positions/frames/[id] with exposure breakdown + fixation timeline + add-fixation dialog
- /positions/import dropzone with preview + commit (idempotency via UUID)
- Global Cmd+K command palette
- 4 Playwright e2e tests: create, add-fixation, over-lock rejection, import flow

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin main
```

## COWORK HANDOFF

Standard format; include bundle sizes per route, Lighthouse scores, and Playwright test count.
