# Phase 12 — Scenario builder + sensitivity + polish insights

> Paste-load: read this file end-to-end, execute every section. Bypass mode is assumed active.

## Context

Phase 12 polishes the analytical surface: users can save / load / delete custom stress scenarios, run live sensitivity analysis (sliders), and export reports. This is the final push before deploy (Phase 13).

Reference:
- Phase 11 risk dashboard (already in place).
- Backend: `scenarios` table + `POST /risk/stress/custom` (stub in Phase 6, wire here).

## Running mode

`--dangerously-skip-permissions` active. Commit + push to main on validation success.

## Tasks

### 1. Scenarios CRUD backend

`backend/app/api/v1/scenarios.py`:

- `GET /scenarios/templates` → list 4 built-in templates (from `scenarios_templates`), no auth scope.
- `GET /scenarios` → list current user's custom scenarios.
- `POST /scenarios` → create custom scenario (uniq per user+name).
- `GET /scenarios/{id}` → fetch single.
- `PATCH /scenarios/{id}` → update.
- `DELETE /scenarios/{id}` → delete.
- All user-scoped routes require `get_current_user`.

Update `/risk/stress/custom` to accept `scenario_id: UUID` as well as inline payload. If id: load from DB, apply.

### 2. Scenarios page (frontend)

`frontend/src/app/(dashboard)/scenarios/page.tsx`:

- Left column: list of saved scenarios (templates + user-created). Template badge for built-ins.
- Right column: editor pane with 5 shock sliders (CBOT soja, CBOT milho, basis soja, basis milho, FX) in percent, range [-50%, +50%] each.
- Name + description fields.
- Preview panel: live P&L impact on user's current portfolio as sliders change (debounced 200ms, calls `/risk/stress/custom` with inline payload).
- Actions: `Save`, `Save as`, `Apply to Risk page` (navigates to /risk with scenario_id query param), `Delete`.

### 3. Sensitivity slider widget

`frontend/src/components/risk/SensitivitySliders.tsx`:

- Embed in `/risk` page as an optional card (toggle "Sensitivity mode" in stress panel).
- 3 sliders: CBOT (% shock, -30% to +30%), FX, basis.
- Live P&L update on drag (debounced 100ms).
- Output: line chart of P&L vs shock for the 3 factors independently (hold others at 0).

### 4. Scenario lifecycle from /risk

- In `/risk` stress panel → "Save this scenario" button next to custom scenario drawer → opens `SaveScenarioDialog` with name + description fields.
- After save, scenario appears in the `Apply from saved` dropdown next run.

### 5. PDF report enhancement (from Phase 11)

- Include the currently applied custom scenario (if any) in the PDF report.
- Add a "Methodology" appendix page citing Jorion (2006), Hull (2022), Basel III/IV FRTB.

### 6. Tests

- Backend: `tests/integration/test_scenarios_crud.py` — 6 tests covering full CRUD + scenario-id lookup in stress.
- Frontend Playwright: `scenarios.spec.ts` — create, save, apply, delete flow.

## Constraints

- Scenario uniqueness: DB CHECK (user_id, name) already enforced in Phase 2 migration.
- Shock slider range validated both client + server (Pydantic `confloat(ge=-0.5, le=0.5)`).
- Sensitivity sliders: debounce 100-200ms to keep requests sane.

## MANDATORY validation

1. Backend mypy + ruff + pytest (full suite + `--run-integration`)  → all pass
2. Frontend lint + typecheck + build + Playwright  → all pass
3. Manual:
   - `/scenarios` → create custom scenario → save → reopen → edit → delete
   - `/risk` → stress panel → "Save this scenario" → confirm it appears in /scenarios list
   - Sensitivity slider → live P&L updates
   - PDF export includes the applied scenario block

Invariants:
- [ ] CRUD on scenarios works end-to-end
- [ ] `/risk/stress/custom` accepts both inline payload AND scenario_id
- [ ] Save-from-risk-page → appears in /scenarios list
- [ ] Sensitivity sliders responsive (< 300ms from drag to chart update)
- [ ] PDF report renders scenario block when applied

## Commit + push

```bash
git add -A
git commit -m "feat(scenarios): Phase 12 — scenario builder + sensitivity + PDF enhancements

- /scenarios CRUD page with shock sliders + live preview
- scenarios_api: GET/POST/PATCH/DELETE endpoints (user-scoped)
- /risk/stress/custom accepts scenario_id for saved-scenario lookup
- SensitivitySliders widget in /risk with 3 single-factor lines
- Save-from-risk-page flow (SaveScenarioDialog)
- PDF report includes applied scenario block + methodology appendix
- 6 backend integration + 1 Playwright e2e

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin main
```

## COWORK HANDOFF

Standard format.
