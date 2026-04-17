# Phase 11 — Risk dashboard (hero page for portfolio)

> Paste-load: read this file end-to-end, execute every section. Bypass mode is assumed active.

## Context

Phase 11 is **the hero page** — the screen recruiters will see first. KPIs, exposure decomposition, VaR / CVaR with method toggle, stress scenarios, MC fan chart, correlation heatmap, attribution table. Must look professional, load fast, and explain methodology via tooltips.

Reference:
- `CLAUDE.md` — Risk Metrics.
- Backend endpoints: `/risk/var`, `/risk/cvar`, `/risk/stress/*`, `/risk/mc/fan`, `/risk/correlation`, `/risk/attribution`.
- Recharts docs for charts.

## Running mode

`--dangerously-skip-permissions` active. Commit + push to main on validation success.

## Design principles

- Two-column grid on desktop (60/40 split), stack on mobile (<768px).
- Every chart has: title + subtitle + info `Tooltip` explaining methodology + "Last updated" timestamp.
- Formatters:
  - `formatBRL(value)` — `pt-BR` locale, 2 decimals (R$ 1.234.567,89).
  - `formatUSD(value)` — $ 1,234,567.89.
  - `formatPercent(value, decimals=2)`.
  - `formatUScBu`, `formatTons`.
- Semantic colors: green for profit, red for loss, amber for warning. CSS variables for theme consistency.
- Recharts only — no D3.
- Loading states: `Skeleton` cards.
- Error boundaries with retry button.

## Tasks

### 1. Dashboard overview (`/dashboard`)

`frontend/src/app/(dashboard)/page.tsx`:

**Row 1 — 4 KPI cards:**
- Total MTM (BRL): sum of all positions' unrealized P&L.
- Open positions count.
- Net CBOT Delta (BRL/ton).
- Net FX Delta (BRL/0.01 BRL/USD).

**Row 2 — Exposure Waterfall** (custom bar chart):
- X-axis: `CBOT_soja`, `CBOT_milho`, `basis_soja`, `basis_milho`, `fx`.
- Y-axis: net exposure in BRL (signed; positive = long, negative = short).
- Color: green for long, red for short.
- Tooltip on bar: decomposition by contributing positions.

**Row 3 — MTM time series:**
- Line chart, last 30 days of portfolio MTM.
- Tooltip on hover: date, value, daily change.

**Row 4 — Two columns (50/50):**
- Left: Concentration Pie (by commodity, by side, by instrument family — toggleable).
- Right: VaR summary card with method toggle (historical / parametric / MC), confidence selector (90/95/97.5/99), horizon toggle (1d/10d). Shows flat + per-leg breakdown (3 sub-numbers).

### 2. Risk deep dive (`/risk`)

`frontend/src/app/(dashboard)/risk/page.tsx`:

**Header controls (sticky):**
- Method switcher: historical / parametric / MC.
- Confidence slider: 90, 95, 97.5, 99.
- Horizon toggle: 1d, 5d, 10d.

**Row 1 — VaR + CVaR cards:**
- `VaRCard`: flat VaR + 3 per-leg breakdown.
- `CVaRCard`: same, with subtle distinction (different color / icon).

**Row 2 — MC Fan Chart:**
- Area chart with 5 percentile bands: p5-p95 filled, p25-p75 filled darker, p50 as solid line.
- X-axis: days `t=0` to `t=horizon`.
- Y-axis: portfolio P&L (BRL).
- Tooltip shows all 5 percentiles at hovered day.

**Row 3 — Stress Panel:**
- 4 cards for the 4 historical scenarios (GFC, drought, COVID, Ukraine).
- Each card: total P&L, per-commodity breakdown (bar), per-leg breakdown (bar).
- **Toggle:** "Linear decomposition" / "Full revaluation" — explains the difference in a tooltip (Phase 6 open question).
- Button: "Run custom scenario" → opens a drawer with sliders for CBOT_soja, CBOT_milho, basis, FX; live P&L preview on drag.

**Row 4 — VaR Attribution Table:**
- Positions sorted desc by contribution_brl.
- Columns: position label, family, contribution_brl, share_pct (with inline progress bar).
- Property check visible: "Σ contributions = R$ XX (flat VaR: R$ XX)" footer.

**Row 5 — Correlation Heatmap:**
- 5×5 matrix of factor correlations.
- Cell colors: red (-1) → white (0) → green (+1).
- Cell labels: correlation value to 2 decimals.
- Window selector: 30d / 90d / 252d.

### 3. PDF export

`frontend/src/components/risk/ExportReportButton.tsx`:

- Button in `/risk` top-right: "Export PDF".
- Click → call `POST /api/v1/reports/risk-pdf` (new endpoint).
- Backend side: new `app/api/v1/reports.py` generating PDF via `reportlab` or `weasyprint` (add `reportlab>=4` to deps). Includes: date, portfolio summary, VaR table, stress table, attribution top 10, exposure waterfall rendered as SVG.

### 4. Formatters module

`frontend/src/lib/formatters/index.ts`:
- Export: `formatBRL`, `formatUSD`, `formatPercent`, `formatUScBu`, `formatTons`.
- All use `Intl.NumberFormat` with `pt-BR` locale.

### 5. E2E tests

`frontend/e2e/risk.spec.ts`:
- `dashboard-loads`: all widgets render without skeleton after 3s.
- `method-switch`: change VaR method → number updates within 2s.
- `mc-fan-monotone`: p5 ≤ p25 ≤ p50 ≤ p75 ≤ p95 at every x-point.
- `stress-toggle-linear-vs-full`: switching modes shows different numbers.
- `pdf-export`: click export → non-empty .pdf file downloads.

## Constraints

- NO inline hex colors — use CSS variables only.
- Charts must be responsive (`ResponsiveContainer`).
- All widgets read via TanStack Query with `staleTime: 60_000` (1 min).
- Refetch on window focus.
- No cumulative layout shift (CLS < 0.1).

## MANDATORY validation

1. `cd frontend && pnpm lint`  → 0 errors
2. `cd frontend && pnpm typecheck`  → 0 errors
3. `cd frontend && pnpm build`  → successful, `/dashboard` chunk < 400 KB gzip, `/risk` < 500 KB gzip
4. `cd backend && uv run pytest tests/integration/test_reports.py --run-integration -v`  → PDF endpoint returns valid PDF
5. Playwright e2e/risk.spec.ts  → all pass
6. Lighthouse on `/dashboard` and `/risk`: perf ≥ 90, a11y ≥ 95, CLS < 0.1
7. Manual:
   - Load `/dashboard` — all 7 widgets render in < 2s (after cache warm)
   - `/risk` method switcher changes numbers coherently
   - MC fan chart animates in; percentiles monotone
   - Stress panel: custom scenario drawer with live preview
   - PDF export downloads non-empty file

Invariants:
- [ ] 7 dashboard widgets render
- [ ] VaR method switcher works
- [ ] MC fan chart monotone
- [ ] Stress linear/full toggle visible and works
- [ ] Attribution table: footer sum matches flat VaR
- [ ] Correlation heatmap 5×5 symmetric, diagonal 1.0
- [ ] PDF export produces valid file
- [ ] Lighthouse thresholds met

## Commit + push

```bash
git add -A
git commit -m "feat(frontend+backend): Phase 11 — risk dashboard hero + PDF export

- /dashboard: 4 KPI cards + exposure waterfall + MTM time series + concentration pie + VaR summary
- /risk: method/confidence/horizon controls + VaR/CVaR cards + MC fan chart + stress panel (linear/full toggle) + attribution table + correlation heatmap
- lib/formatters: BRL/USD/% with pt-BR locale
- backend app/api/v1/reports.py: PDF generation via reportlab
- 5 Playwright e2e tests for dashboard + risk flows

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin main
```

## COWORK HANDOFF

Standard format; include Lighthouse scores, bundle sizes, and 1-2 screenshot descriptions of the dashboard and risk page.
