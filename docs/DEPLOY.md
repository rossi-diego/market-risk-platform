# Deployment Runbook

Production stack:
- **Supabase** — Postgres, Auth, Storage (region `sa-east-1`, project `market-risk-platform-prod`).
- **Render** (free tier) — FastAPI backend, auto-deploy from `main`.
- **Vercel** — Next.js frontend, auto-deploy from `main`.
- **GitHub Actions** — CI (PR lint/test/build) + prod-deploy workflow.

## 1. Supabase production project

> Provisioned via Cowork + Supabase MCP. Keep a screenshot of the project's API credentials page in 1Password.

### First time setup

1. From Cowork, ask:
   ```
   Create a new Supabase project in sa-east-1 called market-risk-platform-prod.
   ```
2. After the project is ready, apply migrations in order (Cowork uses `apply_migration`):
   ```
   supabase/migrations/20260416000001_instruments_schema.sql
   supabase/migrations/20260416000002_rls_policies.sql
   supabase/migrations/20260416000003_seed_scenario_templates.sql
   supabase/migrations/20260416000004_advisor_polish.sql
   ```
3. Run advisors:
   ```
   get_advisors type=security
   get_advisors type=performance
   ```
   Expected: empty or only informational notices.
4. Generate TypeScript types for the frontend:
   ```
   generate_typescript_types → frontend/src/lib/supabase/database-types.ts
   ```
5. Record the credentials:
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `SUPABASE_JWT_SECRET`
   - `DATABASE_URL` (use the **Transaction pooler** URL with `?pgbouncer=true`)

### Rotate keys

- Supabase Studio → Settings → API → *Reset Service Role Key*. Paste the new value into Render's env vars and Vercel's env vars; redeploy both.

## 2. Render — backend

Backend is a standard Python web service.

### Create

1. New → Web Service → connect the `rossi-diego/market-risk-platform` repo.
2. Root directory: `backend`.
3. Runtime: `Python 3`.
4. Build command: `pip install uv && uv sync`.
5. Start command: `uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
6. Health check path: `/api/v1/health`.
7. Region: São Paulo (closest to Supabase `sa-east-1`).

### Env vars (Render → Environment)

```
APP_VERSION=0.1.0
LOG_LEVEL=INFO
MC_SEED=42
ENVIRONMENT=production
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_JWT_SECRET=...
DATABASE_URL=postgresql+asyncpg://...?sslmode=require
CORS_ORIGINS=https://<your-vercel-domain>.vercel.app
SENTRY_DSN=<optional — the backend project DSN>
SENTRY_TRACES_SAMPLE_RATE=0.05
RATE_LIMIT_RISK=60/minute
```

### Auto-deploy from main

- Toggle *Auto-Deploy: Yes* in Render. Every push to `main` that touches `backend/**` triggers a deploy.
- GitHub Actions also calls a Render deploy hook as a belt-and-suspenders step (see
  `.github/workflows/prod-deploy.yml`). To enable that, set the repo variable `RENDER_DEPLOY_HOOK_SET=true` and the secret `RENDER_DEPLOY_HOOK=https://api.render.com/deploy/srv-…?key=…`.

### Cold starts

Render free tier spins the service down after 15 min of idle. First request after idle takes ~30 s. For portfolio demos this is acceptable; to remove it migrate to Fly.io or Railway.

## 3. Vercel — frontend

### Create

1. From Cowork, ask:
   ```
   Create a Vercel project linked to rossi-diego/market-risk-platform,
   root directory frontend/, framework Next.js.
   ```
2. Set environment variables in Vercel:
   ```
   NEXT_PUBLIC_SUPABASE_URL=...
   NEXT_PUBLIC_SUPABASE_ANON_KEY=...
   NEXT_PUBLIC_API_URL=https://<render-subdomain>.onrender.com/api/v1
   NEXT_PUBLIC_SENTRY_DSN=<optional — frontend Sentry DSN>
   ```
3. Trigger the first deploy (`deploy_to_vercel`). Subsequent deploys are automatic on push to `main`.

### Preview URLs

Vercel automatically builds each PR. Add a required status check for `Vercel Preview` in branch-protection rules so unmerged branches must pass.

## 4. GitHub branch protection

Under Settings → Branches → `main`:
- Require a pull request before merging.
- Require status checks: `CI / backend`, `CI / frontend`, `Vercel Preview`.
- Require branches to be up to date before merging.
- Do not allow force pushes.

## 5. Post-deploy smoke test

From any laptop:
```bash
cd backend
uv run --env-file .env.prod python scripts/smoke_prod.py \
    --url https://<render-subdomain>.onrender.com
```

This hits `/api/v1/health`, runs `scripts/db_smoke.py`, and `scripts/fetch_prices.py --dry-run`. All three must be green before promoting.

## 6. Rollback

### Code

```bash
git revert <bad-sha>
git push origin main
```
Render + Vercel redeploy in under a minute. GitHub Actions CI must pass for the revert commit first — do not force-push a broken revert.

### Data

Supabase does not expose branch rollbacks on free tier. Destructive data rollback requires:
```sql
-- From the Supabase SQL editor (DESTRUCTIVE):
truncate prices restart identity cascade;
```
For structured data issues, restore from the most recent daily backup (Settings → Database → Backups → Restore). Supabase retains 7 days of daily backups on free tier.

## 7. Monitoring

- **Sentry**: https://sentry.io/organizations/<org>/projects/ — gated by `SENTRY_DSN`. Separate backend + frontend projects recommended.
- **Render logs**: Dashboard → service → Logs tab. Structured JSON per request line (see `docs/OBSERVABILITY.md`).
- **Vercel logs**: Dashboard → project → Logs. Includes middleware + server component traces.
- **GitHub Actions**: Repo → Actions tab. Watch for red X on `main` — those need a human within 24 h.
