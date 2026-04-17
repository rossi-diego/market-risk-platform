# market-risk-platform

Production-grade web application for market risk analysis of long/short positions in soybean
and corn across physical contracts, CBOT derivatives, basis forwards, and FX derivatives.

## Quick links

- [`CLAUDE.md`](./CLAUDE.md) — project charter, domain model, stack, conventions.
- [`docs/BUILD_PLAN.md`](./docs/BUILD_PLAN.md) — phased delivery plan.
- [`docs/adr/0000-index.md`](./docs/adr/0000-index.md) — architecture decision records.

## Local dev quickstart

### Backend (FastAPI)

```bash
cd backend
cp .env.example .env          # fill in real Supabase values
uv sync
uv run uvicorn app.main:app --reload
# http://localhost:8000/api/v1/health
```

### Frontend (Next.js)

```bash
cd frontend
cp .env.example .env.local    # fill in real Supabase values
pnpm install
pnpm dev
# http://localhost:3000
```

### Infra (Postgres for local experimentation)

```bash
docker compose -f infra/docker-compose.yml up -d postgres
```

Airflow is stubbed in the compose file and will be activated in Phase 4.

## Supabase

> Supabase dev project must be provisioned separately — see Phase 1 handoff.

The backend expects `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`,
`SUPABASE_JWT_SECRET`, and `DATABASE_URL` from an `.env` file (see `backend/.env.example`).
