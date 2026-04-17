# Phase 5 — Position CRUD + Excel import

> Paste-load: read this file end-to-end, execute every section. Bypass mode is assumed active.

## Context

Phase 5 exposes the full FastAPI surface for positions: CRUD on the 4 instrument families, nested fixations under frames, Excel/CSV bulk import, and JWT-gated endpoints. Over-fix protection, status recompute, and atomic imports are all server-side invariants.

Reference:
- `CLAUDE.md` — Instrument Schema, Fixation Modes, API conventions.
- `.claude/skills/supabase-fastapi-async/SKILL.md` (JWT validation, RLS interplay, pagination).
- `docs/adr/0001-instrument-model.md`, `0002-fixacao-model.md`.
- `docs/BUILD_PLAN.md` Phase 5 section (reference only).

## Running mode

`--dangerously-skip-permissions` active. Commit + push to main on validation success.

## Tasks

### 1. Supabase JWT validation

`backend/app/core/security.py`:

- `class UserPrincipal(BaseModel)`: `id: UUID`, `email: str`, `role: str = "authenticated"`.
- `async def get_current_user(authorization: str = Header(...)) -> UserPrincipal`:
  - Reject missing or malformed bearer token with 401.
  - Decode JWT with `jose.jwt.decode(token, settings.SUPABASE_JWT_SECRET, algorithms=["HS256"], audience="authenticated")`.
  - On decode failure: 401 with RFC 7807 Problem Details body (`type`, `title`, `status`, `detail`).
  - Extract `sub` (UUID) as `id`, `email`, `role` from claims.
  - Return `UserPrincipal`.
- FastAPI dependency: every v1 router (except `/health` and `/imports/template`) requires `Depends(get_current_user)`.

### 2. Physical frames + fixations

`backend/app/api/v1/physical.py`:

- `router = APIRouter(prefix="/physical", tags=["physical"])`.
- Endpoints:
  - `GET /frames` — paginated (`limit`, `offset`, `status` filter). Returns `list[PhysicalFrameOut]` with aggregated leg rollups (compute via `open_exposure_frame` — expose `open_cbot_tons`, `open_basis_tons`, `open_fx_tons` in a dedicated `PhysicalFrameWithExposureOut` schema).
  - `POST /frames` — body `PhysicalFrameIn`, returns 201 + `PhysicalFrameOut`. Logs a `trade_events` row with `event_type='open'` in the same transaction.
  - `GET /frames/{frame_id}` — returns `PhysicalFrameDetailOut` (includes nested fixations). 404 if not owned.
  - `PATCH /frames/{frame_id}` — allowed fields: `counterparty`, `notes`, `status`. Other fields return 400.
  - `DELETE /frames/{frame_id}` — soft-fail if fixations exist; require explicit cascade query param `?cascade=true`.
  - `POST /frames/{frame_id}/fixations` — body `PhysicalFixationIn`. Before insert:
    1. Load frame + existing fixations.
    2. Call `open_exposure_frame(frame, existing + [new])` — if it raises `DomainError` (over-lock), return 409 with `{"type":"about:blank","title":"over-locked leg","leg":"cbot","remaining_tons":"700.0000"}`.
    3. Insert inside a transaction.
    4. Call `services.status_recompute.recompute_frame_status(session, frame)` which updates `frames.status` based on cumulative fixations.
    5. Log `trade_events` with `event_type='fill'`, `payload={"fixation_id": ..., "mode": ..., "qty": ...}`.
  - `DELETE /fixations/{fixation_id}` — requires fixation owned (via frame.user_id). Recompute frame status. Log `trade_events` with `event_type='adjust'`.

### 3. CBOT / basis / FX routes

Mirror the physical pattern, simpler (no nested children):

- `backend/app/api/v1/cbot.py` — GET list, POST (validates option fields present when instrument is an option type; validates barrier fields when `barrier_option`), GET/PATCH/DELETE by id.
- `backend/app/api/v1/basis.py` — same shape for `BasisForward`.
- `backend/app/api/v1/fx.py` — same shape for `FXDerivative`.

All POSTs log `trade_events` `event_type='open'`. DELETEs (for closing out) log `event_type='close'`.

### 4. Excel/CSV import

`backend/app/services/imports.py`:

- `def parse_workbook(data: bytes) -> ImportPayload` where `ImportPayload` aggregates parsed rows + per-row errors across 4 sheets:
  - Sheet names (case-insensitive): `physical_frames`, `physical_fixations`, `cbot`, `basis`, `fx`.
  - Column alias dict: maps Portuguese aliases (e.g. `commodity` ↔ `commodity`, `side` ↔ `compra/venda` mapped to `buy/sell`, `tons` ↔ `toneladas`, `vencimento` ↔ `maturity_date`, etc.).
  - Each row: try to build the corresponding `*In` Pydantic schema, collect `ValidationError` as row-level errors.
  - Returns `ImportPayload(frames: list[...], fixations: list[...], cbot: list[...], basis: list[...], fx: list[...], errors: list[RowError])`.
- `@dataclass class RowError`: `sheet: str`, `row_index: int`, `errors: list[dict]` (Pydantic error list).

`backend/app/api/v1/imports.py`:

- `POST /imports/preview` (multipart/form-data, field `file: UploadFile`):
  - Calls `parse_workbook`, returns `ImportPreviewResponse { rows_by_sheet, errors, valid_count, invalid_count }`.
  - Does NOT write to DB.
- `POST /imports/commit` body `ImportCommitRequest { payload: ImportPayload, import_id: UUID }`:
  - Idempotency: if `trade_events` already has `event_type='open'` with `payload.import_id = <this>`, return 200 with `{"status":"already_applied"}`.
  - Inside a single transaction:
    - Insert frames first, collect id mapping by a client-provided temp ref (Excel row reference).
    - Insert fixations using the id mapping (frame_id resolved).
    - Insert derivatives (cbot/basis/fx).
    - For each inserted row, write a `trade_events` with `event_type='open'` and `payload={"import_id": ..., "source": "excel"}`.
  - On any error: ROLLBACK, return 422 with the error row details.
- `GET /imports/template` (no auth, returns a pre-generated .xlsx blob as attachment).

### 5. Status recompute service

`backend/app/services/status_recompute.py`:

- `async def recompute_frame_status(session: AsyncSession, frame: PhysicalFrame) -> None`:
  - Sum locked tons per leg across all fixations on the frame.
  - Status logic:
    - 0 fixations → `open`.
    - Any leg has `locked < total` → `partial`.
    - All 3 legs have `locked == total` → `closed`.
  - Update frame.status, flush.
  - Expired is set by a separate cron when `delivery_end` passes (not Phase 5).

### 6. Example import template

`docs/example_import.xlsx`:

- Generate programmatically via `openpyxl` from a Python helper script (`backend/scripts/generate_import_template.py`).
- 4 sheets: `physical_frames` (3 rows), `physical_fixations` (3 rows referencing frames by row number), `cbot` (2 rows including 1 future + 1 EU call), `basis` (2 rows), `fx` (2 rows including 1 NDF + 1 FX option).
- Helper script is run as part of validation step 7 below — output commits to `docs/example_import.xlsx`.

### 7. Integration tests

`backend/tests/integration/test_positions_crud.py`:

- Fixture `test_user_token`: uses Supabase admin API (`requests.post` to `{SUPABASE_URL}/auth/v1/admin/users`) with service_role_key to create a one-off user, return JWT. Delete user in fixture teardown.
- Fixture `client`: `httpx.AsyncClient(app=app, base_url="http://test")`.
- Mark every test `@pytest.mark.integration` — they hit the real DB via RLS with the test user's JWT.

Tests:
- `test_create_physical_frame` — POST a frame, GET list, GET by id, assert fields.
- `test_create_fixation_updates_status` — POST frame 1000t, POST 1 fixation 500t flat → status becomes `partial`.
- `test_create_full_fixation_closes_frame` — POST frame 1000t, POST 1 fixation 1000t flat → status becomes `closed`.
- `test_fixation_over_lock_returns_409` — POST frame 1000t, POST 600t cbot → 201; POST 500t cbot → 409 with `remaining_tons: 400`.
- `test_cbot_option_requires_fields` — POST CBOT `european_option` without `strike` → 422.
- `test_cbot_barrier_requires_fields` — POST CBOT `barrier_option` without `barrier_level` → 422.
- `test_import_preview_returns_errors` — upload a file with 3 valid + 1 invalid row → response shows 3 valid, 1 invalid with row details. DB unchanged.
- `test_import_commit_atomic` — payload with 1 invalid row → 422, DB has 0 rows added (rollback worked).
- `test_import_commit_idempotent` — commit same import_id twice → second returns `already_applied`, only 1 set of rows in DB.

### 8. Main.py wiring

Update `backend/app/main.py`:

- Include routers: `physical`, `cbot`, `basis`, `fx`, `imports`.
- Add `TrustedHostMiddleware` (only allow `localhost` and `.vercel.app` in dev).
- Wire structured logging middleware (logs `request_id`, `user_id` when available, `duration_ms`, `status_code`).

## Constraints

- Every non-health endpoint MUST require `Depends(get_current_user)`.
- RLS policies on Supabase already enforce per-user isolation. Rely on them — DO NOT duplicate the filter in application code, but DO ensure the session connects with the user's JWT in `Authorization` header (via `session.execute(text("set local role authenticated; set local request.jwt.claims = ..."))`).
- Alternative (simpler for MVP): use `SUPABASE_SERVICE_ROLE_KEY` for the backend connection and add `where user_id = :user_id` explicitly on every query. Pick this path — document it in the handoff. RLS stays on (defense in depth) but the backend bypasses it with the service role.
- Over-fix check MUST run server-side before insert, not client-side only.
- Import commit MUST be one transaction — all rows or none.

## MANDATORY validation

1. `cd backend && uv run mypy app --strict`  → 0 errors
2. `cd backend && uv run ruff check .`  → clean
3. `cd backend && uv run pytest tests/ -v`  → unit passes, integration skipped by default
4. `cd backend && uv run pytest tests/integration/test_positions_crud.py -v --run-integration`  → all integration tests pass (requires live Supabase + test user creation)
5. `cd backend && uv run python scripts/generate_import_template.py --output ../docs/example_import.xlsx`  → file created, size > 5KB
6. `cd backend && uv run python -c "from openpyxl import load_workbook; wb = load_workbook('../docs/example_import.xlsx'); print('sheets:', wb.sheetnames)"`  → prints all 5 sheets
7. `cd backend && uv run uvicorn app.main:app --port 8001 & sleep 3 && curl -s http://localhost:8001/api/v1/openapi.json | python -c "import sys,json; d=json.load(sys.stdin); print('paths:', len(d['paths']), 'endpoints')" && kill %1`  → prints ≥20 endpoints

Invariants:
- [ ] mypy strict: 0 errors
- [ ] Integration tests all pass (requires live Supabase — document if skipped)
- [ ] All 4 instrument families have CRUD
- [ ] Over-fix returns 409 with remaining_tons
- [ ] Import commit is atomic and idempotent
- [ ] example_import.xlsx exists and loads
- [ ] OpenAPI spec exposes ≥20 endpoints

## Commit + push

```bash
git add -A
git status --short
git commit -m "feat(api): Phase 5 — FastAPI CRUD for 4 instrument families + Excel import

- core/security.py: Supabase JWT validation via get_current_user dependency
- api/v1/physical.py: frames + fixations; over-fix returns 409; status auto-recomputes on fixation change
- api/v1/cbot.py, basis.py, fx.py: full CRUD with option/barrier field validation
- api/v1/imports.py: multi-sheet Excel preview (no-write) + atomic, idempotent commit
- services/imports.py: Portuguese/English column aliasing; row-level Pydantic errors
- services/status_recompute.py: frame.status derived from fixations per 5-mode lock table
- docs/example_import.xlsx: 4-sheet template generated by scripts/generate_import_template.py
- Integration tests cover over-fix, atomic import, idempotency, option field validation

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin main
```

## COWORK HANDOFF

```
=== COWORK HANDOFF — PHASE 5 BEGIN ===

Status: <✅ shipped / ❌ failed>
Mode:   --dangerously-skip-permissions
Date:   <YYYY-MM-DD HH:MM local>

Git state (post-commit):
  branch:       main
  local HEAD:   <sha>
  origin/main:  <sha>
  aligned:      <yes/no>
  tree clean:   <yes/no>

Commit (if shipped):
  SHA:     <sha>
  subject: feat(api): Phase 5 — FastAPI CRUD for 4 instrument families + Excel import
  push:    <paste the "To ... main -> main" line>

Validation matrix:
  [✓/✗] 1. mypy strict                         <N source files, 0 errors | N errors>
  [✓/✗] 2. ruff                                 <clean | N issues>
  [✓/✗] 3. pytest (unit)                        <N/N passed>
  [✓/✗] 4. pytest (integration, --run-integration) <N/N passed | skipped (reason)>
  [✓/✗] 5. example_import.xlsx generated        <size in bytes>
  [✓/✗] 6. example_import.xlsx sheet list       <[sheets]>
  [✓/✗] 7. OpenAPI endpoints count              <N endpoints>

DB access decision (MUST fill):
  Strategy: <RLS per-request with set-local jwt / service_role bypass + application filter>
  Rationale: <one-line explanation>

Files created:
  backend/app/core/:       security.py
  backend/app/api/v1/:     physical.py, cbot.py, basis.py, fx.py, imports.py
  backend/app/services/:   imports.py, status_recompute.py
  backend/scripts/:        generate_import_template.py
  backend/tests/integration/: test_positions_crud.py
  docs/:                   example_import.xlsx

Endpoints by family (from OpenAPI):
  physical: <N endpoints>
  cbot:     <N>
  basis:    <N>
  fx:       <N>
  imports:  <N>

Blockers / errors (if ❌):
  <step number>: <last 20 lines of command output>
  hypothesis: <your best guess at cause>
  scope-of-fix: <within prompt scope / requires Diego / requires Cowork (Supabase config)>

Next expected action (Diego):
  - Open http://localhost:8000/api/v1/docs, authenticate with a test JWT, exercise the endpoints manually (create frame, add fixations, verify 409 on over-lock).
  - Upload docs/example_import.xlsx to /imports/preview, confirm preview shows all rows valid, commit, verify trade_events logged.
  - Return to Cowork for Phase 6 (risk engine: VaR + CVaR + stress).

Open questions for Diego:
  <list or "none">

=== COWORK HANDOFF — PHASE 5 END ===
```
