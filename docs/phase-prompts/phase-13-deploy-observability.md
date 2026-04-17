# Phase 13 — Deploy + observability (MVP ships)

> Paste-load: read this file end-to-end, execute every section. Bypass mode is assumed active.

## Context

Phase 13 ships the MVP to production: Vercel (frontend), Render (backend), Supabase (prod). Plus hardening: Sentry error tracking, structured logs, CI branch protection, pre-deployment smoke tests.

This phase splits between **Cowork MCP** (Supabase prod creation + Vercel deploy) and **Claude Code** (logging + CI + docs). Coordinate accordingly.

Reference:
- `CLAUDE.md` — Infrastructure stack.
- `docs/BUILD_PLAN.md` — Phase 13 section.
- Render docs for Python services.

## Running mode

`--dangerously-skip-permissions` active in Claude Code. Cowork MCP handles Supabase prod + Vercel deploy steps.

## Tasks

### Split 1 — Cowork (do this first)

Ask Cowork to:

1. **Create `market-risk-platform-prod` Supabase project** in `sa-east-1` (separate from dev).
2. **Apply the 4 SQL migrations** from `supabase/migrations/` via `apply_migration` in order.
3. **Run advisors** (security + performance) → expected similar clean output to dev.
4. **Generate TypeScript types**: `generate_typescript_types` → save to `frontend/src/lib/supabase/database-types.ts`.
5. **Return prod credentials**: project URL, anon key, service role key, JWT secret, DATABASE_URL.
6. **Create Vercel project** linked to the repo (frontend/ directory). Set env vars from step 5.
7. **Trigger initial deploy** via `deploy_to_vercel`. Monitor via `get_deployment_build_logs` if it fails.

### Split 2 — Claude Code (do after Cowork returns credentials)

### 1. Structured logging (backend)

`backend/app/core/logging.py` (already exists from Phase 1 — enhance):

- Processors: `add_timestamp`, `add_request_id`, `format_exc_info`, `JSONRenderer`.
- ContextVars: `request_id`, `user_id` populated by middleware per request.
- Configurable via `LOG_LEVEL` env var.

`backend/app/middleware/request_log.py` (new):
- Log each request with: method, path, status, duration_ms, user_id, request_id.
- Upgrade the simple `RequestLoggingMiddleware` from Phase 5 to write structured JSON.

### 2. Sentry integration

Backend:
- Add `sentry-sdk[fastapi]>=2.0` to deps.
- `app/core/sentry.py`: `init_sentry()` called from `app/main.py` lifespan if `SENTRY_DSN` env set.
- Capture unhandled exceptions; scrub PII (email, user_id hash).

Frontend:
- Add `@sentry/nextjs` dep.
- Run `npx @sentry/wizard@latest -i nextjs` once, commit the generated config files.
- `NEXT_PUBLIC_SENTRY_DSN` env var wired.

### 3. CI / CD hardening

`.github/workflows/ci.yml`:
- Already runs lint + test + build from Phase 1. Add:
  - `concurrency` group per branch to cancel stale runs.
  - `cache` for uv + pnpm dependencies.
  - Required status checks for `main` branch protection (Cowork can set this via GitHub API or Diego sets manually).
- New job `deploy-preview` on `pull_request`: deploy frontend to Vercel preview URL + comment on PR.

`.github/workflows/prod-deploy.yml` (new):
- Trigger on push to `main` with paths: `backend/**`.
- Calls Render deploy hook (curl).

### 4. Pre-deployment smoke

`backend/scripts/smoke_prod.py` (new):
- Runs `db_smoke.py` + `fetch_prices.py --dry-run` + health endpoint check against the prod URL.
- Called from CI prod-deploy workflow before promoting.

### 5. Rate limiting

Backend: add `slowapi>=0.1` dep.
- `app/middleware/rate_limit.py`: per-user rate limit (e.g. 60 requests/minute) on `/risk/*` endpoints to prevent runaway MC calls from burning CPU.
- Apply via FastAPI middleware stack.

### 6. CORS hardening for prod

- `app/main.py`: `CORS_ORIGINS` reads from env. In prod `.env`, set to `https://<vercel-domain>`.
- Remove `allow_origins=["*"]` fallback.
- Credentials mode only with specific origins.

### 7. Deploy runbook

`docs/DEPLOY.md` (update or create):

- **Supabase prod**: how to create, apply migrations, rotate keys.
- **Vercel**: how to connect repo, set env vars, promote preview to prod.
- **Render**: create Python web service, set env vars, wire auto-deploy from `main`, health check path.
- **Rollback**: `git revert` + `git push` for code; `supabase db reset` for data (destructive — document clearly).
- **Monitoring**: Sentry dashboard URL, structlog querying, GitHub Actions failures inbox.

## MANDATORY validation

Backend:
1. `uv run mypy app --strict`  → 0 errors
2. `uv run ruff check .`  → clean
3. `uv run pytest --cov=app`  → all pass, coverage baseline maintained
4. `uv run python scripts/smoke_prod.py --url https://<prod-backend>.onrender.com`  → all green

Frontend:
5. `pnpm lint + typecheck + build`  → clean
6. `pnpm playwright test`  → all pass

Deployment:
7. Vercel deploy green (manual check via Cowork `get_deployment` or `get_deployment_build_logs`)
8. Render deploy green (check Render dashboard or `/health` endpoint)
9. Manual: open prod URL, login with a test user, create a position, verify /risk loads

Observability:
10. Trigger a forced error on backend (e.g., malformed JWT request) → Sentry receives event within 60s
11. Check GitHub Actions: last 3 runs passing on main

Invariants:
- [ ] Supabase prod project live + migrations applied
- [ ] Vercel frontend deployed, custom domain or vercel.app URL accessible
- [ ] Render backend deployed, `/health` returns 200
- [ ] End-to-end auth flow works on prod
- [ ] Sentry capturing errors on both FE and BE
- [ ] Rate limiting active on `/risk/*`
- [ ] CORS restricted to prod domain only
- [ ] docs/DEPLOY.md complete
- [ ] Main branch protected (required status checks)

## Commit + push

```bash
git add -A
git commit -m "feat(deploy): Phase 13 — production deploy + observability hardening

- Supabase prod provisioned (sa-east-1), migrations applied, advisors clean
- Vercel frontend deployed from main; preview URLs on PRs
- Render backend deployed with auto-deploy from main
- Sentry wired in backend + frontend (gated by SENTRY_DSN env)
- structlog upgraded with request_id context var + JSON middleware
- slowapi rate limiting on /risk/*
- CORS_ORIGINS locked to prod domain
- docs/DEPLOY.md runbook + docs/OBSERVABILITY.md
- Pre-deploy smoke script (db + yfinance + health)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin main
```

## COWORK HANDOFF

Standard format with:
- Vercel production URL
- Render production URL
- Supabase prod project ref
- Sentry dashboard URL
- Sample log event + Sentry event IDs
