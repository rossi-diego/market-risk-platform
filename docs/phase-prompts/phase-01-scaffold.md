# Phase 1 — Repo scaffold (Claude Code prompt)

> Paste-load instructions for Claude Code: read this file end-to-end, then execute every section in order. Bypass mode is assumed active — do not ask for confirmation.

## Context

Phase 1 of the market-risk-platform build plan.

Reference spec (read these in order before starting):

1. `CLAUDE.md` (project root) — full scope, stack, conventions, repo structure.
2. `docs/BUILD_PLAN.md` — Phase 1 section ONLY is authoritative; later phases are reference-only, do NOT anticipate them.
3. `docs/adr/0001-instrument-model.md`, `0002-fixacao-model.md`, `0003-risk-aggregation.md` — accepted decisions.
4. `.claude/skills/supabase-fastapi-async/SKILL.md` — integration patterns.

**Goal:** scaffold the monorepo so backend runs a healthy FastAPI, frontend runs a Next.js shell, CI/CD skeleton is in place, and tooling (lint/type/test) is wired. No domain code yet — that starts in Phase 3.

## Running mode

You are in `--dangerously-skip-permissions` mode. After all validation passes, you MUST commit and push to `main` autonomously. Do NOT ask for confirmation — it's already granted.

If validation fails at any step, STOP before commit and print the COWORK HANDOFF block with `Status: ❌`.

## Tasks

### 1. `backend/pyproject.toml`

- `[project]`: `name="market-risk-platform-backend"`, `version="0.1.0"`, `requires-python=">=3.12,<3.13"`.
- Runtime dependencies (pin major version, latest minor as of today):
  - `fastapi>=0.115`
  - `uvicorn[standard]>=0.30`
  - `sqlalchemy[asyncio]>=2.0`
  - `asyncpg>=0.29`
  - `alembic>=1.13`
  - `pydantic>=2.7`
  - `pydantic-settings>=2.4`
  - `structlog>=24`
  - `python-jose[cryptography]>=3.3`
  - `passlib[bcrypt]>=1.7`
  - `pandas>=2.2`
  - `openpyxl>=3.1`
  - `numpy>=2`
  - `scipy>=1.13`
  - `yfinance>=0.2`
  - `httpx>=0.27`
- Dev dependencies under `[dependency-groups.dev]` (uv format):
  - `pytest>=8`, `pytest-asyncio>=0.23`, `pytest-cov>=5`
  - `mypy>=1.11`, `ruff>=0.6`
  - `pre-commit>=3.8`
  - `types-python-jose`
- `[tool.ruff]`: `line-length=100`, `target-version="py312"`, `extend-select=["E","F","I","N","W","UP","B","C4","SIM","RUF"]`.
- `[tool.mypy]`: `strict=true`, `python_version="3.12"`, `mypy_path=["app"]`, `exclude=["^migrations/"]`.
- `[tool.pytest.ini_options]`: `asyncio_mode="auto"`, `addopts="--strict-markers --cov=app --cov-report=term-missing"`.

### 2. Backend entrypoint

- `backend/app/__init__.py` — empty.
- `backend/app/main.py`:
  - FastAPI app with CORS middleware sourcing origins from settings.
  - APIRouter mounted at `/api/v1`.
  - `GET /api/v1/health` returns `{"status": "ok", "version": settings.APP_VERSION}`.
  - Startup/shutdown hooks log a structured event via structlog.

### 3. Settings

`backend/app/core/config.py` using pydantic-settings:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_VERSION: str = "0.1.0"
    LOG_LEVEL: str = "INFO"
    MC_SEED: int = 42

    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_JWT_SECRET: str
    DATABASE_URL: str  # postgresql+asyncpg://...
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()  # module-level singleton
```

### 4. Structured logging

`backend/app/core/logging.py`:

- structlog setup with processors: `add_timestamp`, `format_exc_info`, `JSONRenderer`.
- Export `configure_logging(level: str) -> None` invoked from `main.py` startup hook.

### 5. Async DB session

`backend/app/core/db.py`:

- Async SQLAlchemy engine factory from `settings.DATABASE_URL`.
- `async_sessionmaker` bound to the engine.
- `async def get_session()` dependency stub (no models yet — Phase 3 adds them).

### 6. Env example (backend)

`backend/.env.example` (commit this file):

- All keys from `Settings` with `"<replace-me>"` placeholders.
- Header comment pointing users to the Supabase project dashboard for real values.

### 7. Backend health test

- `backend/tests/__init__.py` — empty.
- `backend/tests/test_health.py`:
  - Async test using `httpx.AsyncClient` against the FastAPI app.
  - Asserts `200` + `{"status": "ok", "version": "0.1.0"}`.
  - Use a pytest fixture or `monkeypatch.setenv` to satisfy the required Settings fields (they can be dummy strings for the test).

### 8. Frontend scaffold

Inside a fresh `frontend/` directory via pnpm:

```bash
pnpm create next-app@latest frontend --ts --tailwind --eslint --app --src-dir --import-alias '@/*' --no-turbopack
cd frontend
pnpm add @supabase/supabase-js @supabase/ssr @tanstack/react-query zustand recharts lucide-react date-fns zod react-hook-form @hookform/resolvers
pnpm add -D prettier prettier-plugin-tailwindcss @types/node
pnpm dlx shadcn@latest init   # style=new-york, base color=slate, CSS variables=yes; use --defaults --yes if supported
pnpm dlx shadcn@latest add button card input label form dialog select tabs table badge sonner skeleton separator dropdown-menu tooltip breadcrumb sheet avatar command
```

Additional files:

- `frontend/.env.example`:
  - `NEXT_PUBLIC_SUPABASE_URL=<replace-me>`
  - `NEXT_PUBLIC_SUPABASE_ANON_KEY=<replace-me>`
  - `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1`
- `frontend/.prettierrc.json`:
  - `{"plugins":["prettier-plugin-tailwindcss"],"semi":true,"singleQuote":false,"trailingComma":"all","printWidth":100}`
- `frontend/package.json` scripts additions:
  - `"typecheck": "tsc --noEmit"`
  - `"format": "prettier --write ."`
  - `"format:check": "prettier --check ."`

### 9. Docker compose (infra)

`infra/docker-compose.yml`. Do NOT start services — just author the file.

- Service `postgres`:
  - `image: postgres:16-alpine`
  - env: `POSTGRES_USER=mrp`, `POSTGRES_PASSWORD=mrp_dev`, `POSTGRES_DB=mrp`
  - port `5432:5432`
  - volume `pgdata:/var/lib/postgresql/data`
- Service `airflow` — fully defined but entirely commented out with header `# TODO: uncomment in Phase 4`. Include: `image: apache/airflow:2.9-python3.12`, `depends_on: postgres`, ports `8080:8080`.
- Top-level volumes: `pgdata`.

### 10. GitHub Actions CI

`.github/workflows/ci.yml`:

- `name: CI`
- `on`: `pull_request` and `push` filtered to `main`.
- Jobs:
  - `backend` (runs-on: ubuntu-latest): checkout → setup-python 3.12 → install uv → `cd backend && uv sync` → `uv run ruff check .` → `uv run mypy app/` → `uv run pytest`.
  - `frontend` (runs-on: ubuntu-latest): checkout → setup-node 20 → pnpm/action-setup → `cd frontend && pnpm install --frozen-lockfile` → `pnpm lint` → `pnpm typecheck` → `pnpm format:check` → `pnpm build`.

### 11. Pre-commit

`.pre-commit-config.yaml` at repo root:

- `pre-commit-hooks`: `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-added-large-files`.
- `ruff`: lint + format, scoped to `backend/`.
- `mypy`: scoped to `backend/app/`, `--strict`.
- `prettier`: scoped to `frontend/`, format staged files only.

### 12. README

Replace the current 1-line `README.md` at root with:

- Project title + one-line description.
- Quick links to `CLAUDE.md`, `docs/BUILD_PLAN.md`, `docs/adr/0000-index.md`.
- Local dev quickstart: backend (`uv sync` + `uvicorn`), frontend (`pnpm dev`), docker compose note.
- Explicit note: "Supabase dev project must be provisioned separately — see Phase 1 handoff."

### 13. `.gitattributes`

Create at repo root:

```
* text=auto eol=lf
*.py text eol=lf
*.sh text eol=lf
*.md text eol=lf
```

## Constraints

- Do NOT start any server or container. No `uvicorn run`, no `pnpm dev`, no `docker compose up`. Install, build, lint, type, test only.
- Do NOT create files outside: `backend/`, `frontend/`, `infra/`, `.github/`, `.pre-commit-config.yaml`, `.gitattributes`, `README.md`.
- Do NOT embed secrets in any file.
- If a task requires a decision not specified here, STOP and ask.

## MANDATORY validation

Run in this exact order and capture output. Invariants must hold before committing.

### Backend

1. `cd backend && uv lock`
2. `cd backend && uv sync`
3. `cd backend && uv run ruff check .`
4. `cd backend && uv run mypy app/`
5. `cd backend && uv run pytest -v`
6. `cd backend && uv run python -c "from app.main import app; print(app.title)"`

### Frontend

7. `cd frontend && pnpm install` — first run creates lockfile.
8. `cd frontend && pnpm install --frozen-lockfile` — second run confirms determinism.
9. `cd frontend && pnpm lint`
10. `cd frontend && pnpm typecheck`
11. `cd frontend && pnpm format:check`
12. `cd frontend && pnpm build`

### Tooling

13. `pre-commit install`
14. `pre-commit run --all-files` — re-run once if first run auto-fixed.

### Tree sanity

15. `tree -L 3 -I 'node_modules|.venv|.next|.ruff_cache|.mypy_cache|__pycache__|.pytest_cache' 2>/dev/null || find . -maxdepth 3 -type d -not -path '*/node_modules*' -not -path '*/.venv*' -not -path '*/.next*' -not -path '*/.git*' | sort`

### Secrets scan

16. `git grep -iE '(supabase_service_role_key|api_key|secret|password|token)\s*=\s*["a-zA-Z0-9]{10,}' -- ':!*.example' ':!CLAUDE.md' ':!docs/' ':!.claude/'`
    — expect no matches (exit code 1 from grep = good).

### Invariants — ALL must be true before committing

- [ ] Steps 1–16 each return success per the expected output in comments.
- [ ] `frontend/src/components/ui/` has ≥19 `.tsx` files (shadcn components installed).
- [ ] `backend/tests/test_health.py` passes (1/1).
- [ ] No files exist outside the declared scope.
- [ ] No secret-like values in tracked content (step 16 clean).

If **all** invariants hold → proceed to commit + push phase.
If **any** invariant fails → STOP, do NOT commit, jump to COWORK HANDOFF with `Status: ❌` and full details.

## Commit + push (only if all invariants hold)

```bash
git add -A
git status --short   # capture for handoff
git commit -m "feat(scaffold): Phase 1 — backend + frontend + CI + tooling

- Backend: FastAPI 0.115 + SQLAlchemy 2.0 async + uv deps; health endpoint at /api/v1/health
- Frontend: Next.js 14 App Router + pnpm + Tailwind + shadcn/ui (19 components)
- Infra: Docker Compose (postgres live, airflow stubbed for Phase 4)
- CI: GitHub Actions running ruff + mypy + pytest (backend) and lint + tsc + build (frontend)
- Tooling: pre-commit (ruff, mypy, prettier, hygiene); .gitattributes normalizes line endings

Supabase dev project to be provisioned via Cowork MCP in next step.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin main   # capture for handoff
```

Capture the commit SHA and the push summary line.

## COWORK HANDOFF

Print this EXACT block at the end of the session, replacing placeholders. Diego will copy everything from the `BEGIN` marker to the `END` marker (inclusive) and paste into Cowork.

```
=== COWORK HANDOFF — PHASE 1 BEGIN ===

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
  subject: feat(scaffold): Phase 1 — backend + frontend + CI + tooling
  push:    <paste the "To ... main -> main" line>

Validation matrix:
  [✓/✗] 1. uv lock                       <one-line result>
  [✓/✗] 2. uv sync                       <one-line result>
  [✓/✗] 3. ruff check                    <one-line result>
  [✓/✗] 4. mypy --strict                 <N source files, 0 errors | N errors>
  [✓/✗] 5. pytest                        <N/N passed>
  [✓/✗] 6. backend import smoke          <app title | error>
  [✓/✗] 7. pnpm install                  <success | error>
  [✓/✗] 8. pnpm install --frozen         <success | error>
  [✓/✗] 9. pnpm lint                     <0 errors | N errors>
  [✓/✗] 10. pnpm typecheck               <0 errors | N errors>
  [✓/✗] 11. pnpm format:check            <clean | N files unformatted>
  [✓/✗] 12. pnpm build                   <success with N routes | error>
  [✓/✗] 13. pre-commit install           <installed | error>
  [✓/✗] 14. pre-commit run --all-files   <all hooks pass | N failed>
  [✓/✗] 15. tree sanity                  <OK | scope violation>
  [✓/✗] 16. secrets scan                 <clean | N matches>

Files created (summary):
  backend/:   <list>
  frontend/:  Next.js scaffold + <N> shadcn components + .env.example + .prettierrc.json
  infra/:     docker-compose.yml
  .github/:   workflows/ci.yml
  root:       .pre-commit-config.yaml, .gitattributes, README.md (replaced)

Blockers / errors (if ❌):
  <step number>: <last 20 lines of command output>
  hypothesis: <your best guess at cause>
  scope-of-fix: <within prompt scope / requires Diego>

Next expected action (Diego):
  - Manually test: `cd backend && uv run uvicorn app.main:app --reload` → open http://localhost:8000/api/v1/health
  - Manually test: `cd frontend && pnpm dev` → open http://localhost:3000
  - Return to Cowork and say "Cowork: cria o Supabase"

Open questions for Diego:
  <list or "none">

=== COWORK HANDOFF — PHASE 1 END ===
```
