# Phase 4 — Price ingestion (yfinance + cron + Airflow DAG)

> Paste-load: read this file end-to-end, execute every section. Bypass mode is assumed active.

## Context

Phase 4 builds the price pipeline: fetch `ZS=F`, `ZC=F`, `USDBRL=X` from yfinance daily at 18:00 BRT, validate, and upsert to `prices`. Two runners: GitHub Actions cron (primary, always on) and Airflow DAG (local, portfolio piece).

Reference:
- `CLAUDE.md` — Data Sources & Update Schedule.
- `.claude/skills/airflow-price-pipeline/SKILL.md`.
- `.claude/skills/commodity-price-decomposition/SKILL.md` (price_source flags).

## Running mode

`--dangerously-skip-permissions` active. Commit + push to main on validation success.

## Tasks

### 1. Price ingestion service

`backend/app/services/price_ingestion.py`:

- `@dataclass(frozen=True) class PriceRecord`: `observed_at: datetime`, `instrument: str`, `commodity: Commodity | None`, `value: Decimal`, `unit: str`, `price_source: PriceSource`.
- `def fetch_cbot_soja() -> PriceRecord` — `yfinance.Ticker("ZS=F").history(period="5d")`, last row's close, `price_source=YFINANCE_CBOT`, `commodity=SOJA`, `unit="USc/bu"`.
- `def fetch_cbot_milho() -> PriceRecord` — `ZC=F`, `price_source=CBOT_PROXY_YFINANCE` (flag the proxy clearly), `commodity=MILHO`.
- `def fetch_fx_usdbrl() -> PriceRecord` — `USDBRL=X`, `price_source=YFINANCE_FX`, `commodity=None`, `unit="BRL/USD"`.
- `def fetch_all() -> list[PriceRecord]` — calls the three above, returns list of 3.
- `def validate_records(records: list[PriceRecord], max_staleness_days: int = 5) -> list[PriceRecord]`:
  - Rejects with structured log + `ValueError` if: `value <= 0`, `observed_at` older than `now() - max_staleness_days` business days.
  - Uses structlog with keys: `instrument`, `value`, `observed_at`, `price_source`.
- `async def upsert_prices(session: AsyncSession, records: list[PriceRecord]) -> int`:
  - Uses `INSERT ... ON CONFLICT (observed_at, instrument) DO UPDATE SET value = EXCLUDED.value, price_source = EXCLUDED.price_source`.
  - Returns count of rows affected.

### 2. CLI entrypoint

`backend/scripts/fetch_prices.py`:

- argparse:
  - `--dry-run` — fetch + validate, print table, no DB write.
  - `--date YYYY-MM-DD` — override "today" for backfill (yfinance returns the nearest trading-day record anyway).
  - `--verbose` — log level DEBUG.
- Main flow:
  1. `configure_logging()`
  2. `records = fetch_all()`
  3. `records = validate_records(records)`
  4. If `--dry-run`: print table of records, exit 0.
  5. Else: open async session, `await upsert_prices(session, records)`, commit.
  6. Log summary: `{"event": "price_update_complete", "upserted": N, "duration_ms": ...}`.
- Exit 0 on success, non-zero on any exception with structured error log.

Shebang, module guard (`if __name__ == "__main__": asyncio.run(main())`).

### 3. GitHub Actions cron

`.github/workflows/price_update.yml`:

- `name: Price update`
- Triggers:
  - `schedule: - cron: '0 21 * * 1-5'` — 21:00 UTC = 18:00 BRT weekdays.
  - `workflow_dispatch:` with inputs: `date` (optional), `dry_run` (boolean, default false).
- Job `update`:
  - `runs-on: ubuntu-latest`.
  - Concurrency group `price-update` to prevent overlapping runs.
  - Steps:
    1. checkout.
    2. Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`, add to PATH.
    3. Setup Python 3.12.
    4. `cd backend && uv sync --frozen`.
    5. Run: `cd backend && uv run python scripts/fetch_prices.py ${{ inputs.dry_run && '--dry-run' || '' }} ${{ inputs.date && format('--date {0}', inputs.date) || '' }}`.
    6. On failure: use `actions/github-script` to create an issue with title `Price update failed ${{ github.run_id }}` and body containing the last 100 lines of logs (fetch via `actions/upload-artifact` + download not needed; use the step outputs directly).
  - Secrets injected as env: `DATABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `LOG_LEVEL=INFO`, `MC_SEED=42`.

### 4. Airflow DAG (portfolio artifact)

`infra/airflow/dags/commodity_price_pipeline.py`:

- DAG definition:
  - `dag_id = "commodity_price_pipeline"`
  - `schedule = "0 18 * * 1-5"` (local Airflow timezone will be America/Sao_Paulo via `default_args` timezone)
  - `catchup=False`, `max_active_runs=1`, `tags=["commodity", "market-risk"]`.
  - `default_args = {"retries": 2, "retry_delay": timedelta(minutes=5), "owner": "diego"}`.
- Tasks (TaskFlow API):
  1. `fetch_soy` — calls `fetch_cbot_soja()`, XCom-pushes the record.
  2. `fetch_corn` — calls `fetch_cbot_milho()`.
  3. `fetch_fx` — calls `fetch_fx_usdbrl()`.
  4. `validate` — pulls 3 records, calls `validate_records([...])`.
  5. `upsert_supabase` — opens session, calls `upsert_prices(...)`.
  6. `trigger_mtm_recalc` — HTTP POST to `{API_URL}/api/v1/risk/recalculate` (stubbed endpoint introduced in Phase 6; for now just logs a no-op and returns success).
- Dependencies: `fetch_soy >> validate`, `fetch_corn >> validate`, `fetch_fx >> validate`, `validate >> upsert_supabase >> trigger_mtm_recalc`.
- Docstrings on the DAG and each task.
- IMPORTANT: DAG must parse without connection errors on Claude Code machine (no real Airflow server needed — just ensure the Python file is syntactically valid and DAG objects are instantiable).

### 5. Integration test

`backend/tests/integration/__init__.py` — empty.
`backend/tests/integration/test_price_ingestion.py`:

- Uses `pytest-mock` (`pnpm add -D`... wait, pytest-mock is a backend dep — add `pytest-mock>=3.14` to dev deps in `pyproject.toml` if missing).
- Monkeypatches `yfinance.Ticker` with a stub returning a known DataFrame.
- Tests:
  - `test_fetch_cbot_soja_returns_record` — price_source is `YFINANCE_CBOT`, unit is `USc/bu`, commodity is `SOJA`.
  - `test_fetch_cbot_milho_uses_proxy_flag` — price_source is `CBOT_PROXY_YFINANCE`.
  - `test_validate_rejects_zero_or_negative` — value=0 or value=-1 → `ValueError`.
  - `test_validate_rejects_stale` — observed_at > 5 business days ago → `ValueError`.
  - `test_upsert_idempotent` — requires a test DB (use a pytest fixture with a disposable Supabase branch OR skip if `SUPABASE_URL` env not set — document the skip). Two calls with same `(observed_at, instrument)` result in 1 row (not 2).
  - `test_upsert_updates_on_conflict` — second call with different `value` updates the existing row.
- For the integration tests that need DB: mark with `@pytest.mark.integration` and configure pytest to skip them unless `--run-integration` flag is passed (add to `conftest.py`).

### 6. Conftest helpers

`backend/tests/conftest.py`:

- `pytest_addoption` adds `--run-integration` flag.
- `pytest_collection_modifyitems` skips `@pytest.mark.integration` unless flag passed.

## Constraints

- Do NOT commit any secrets. The GHA workflow uses `${{ secrets.* }}`.
- Do NOT actually execute the Airflow DAG or cron workflow from Claude Code.
- Do NOT hit the real Supabase DB from the unit tests (`test_fetch_*` and `test_validate_*` must be pure). Only `test_upsert_*` are integration and skip by default.
- All yfinance calls in unit tests must be mocked — no network from `pytest` without `--run-integration`.

## MANDATORY validation

1. `cd backend && uv run mypy app/services app/risk scripts --strict`  → 0 errors
2. `cd backend && uv run ruff check .`  → clean
3. `cd backend && uv run pytest tests/ -v`  → all pass (integration tests skipped OK)
4. `cd backend && uv run python scripts/fetch_prices.py --dry-run`  → prints 3 PriceRecord rows, exits 0 (requires network; if offline, note as OPEN QUESTION, do NOT fail validation)
5. `cd infra/airflow/dags && python -c "import commodity_price_pipeline; print('dag imports ok'); print([t.task_id for t in commodity_price_pipeline.dag.tasks])"`  → prints 6 task IDs OR skip if Airflow libs not installed in the CC environment (install `apache-airflow>=2.9` temporarily if needed, otherwise document in OPEN QUESTIONS).
6. `cd backend && yamllint ../.github/workflows/price_update.yml || actionlint ../.github/workflows/price_update.yml || echo "yamllint/actionlint not installed — YAML parsed by Python instead"; python -c "import yaml; yaml.safe_load(open('../.github/workflows/price_update.yml'))"`  → no YAML parse errors
7. `git grep -iE '(supabase_service_role_key|api_key|secret|password|token)\s*=\s*["a-zA-Z0-9]{10,}' -- ':!*.example' ':!docs/' ':!.claude/'`  → no matches

Invariants:
- [ ] mypy strict: 0 errors
- [ ] Unit tests pass (ingestion logic + mocks)
- [ ] `fetch_prices.py --dry-run` outputs 3 rows (or flagged in OPEN QUESTIONS if network blocked)
- [ ] Airflow DAG file parses and has 6 tasks (or flagged if Airflow not installed)
- [ ] Price update workflow YAML is valid
- [ ] No secrets in tracked content
- [ ] `price_source` flags correct: `ZS=F → YFINANCE_CBOT`, `ZC=F → CBOT_PROXY_YFINANCE`, `USDBRL=X → YFINANCE_FX`

## Commit + push

```bash
git add -A
git status --short
git commit -m "feat(ingestion): Phase 4 — yfinance pipeline + GHA cron + Airflow DAG

- app/services/price_ingestion.py: fetch ZS=F, ZC=F (proxy-flagged), USDBRL=X; validate + upsert with ON CONFLICT
- scripts/fetch_prices.py: CLI with --dry-run, --date, --verbose
- .github/workflows/price_update.yml: cron 21:00 UTC (18:00 BRT) + manual dispatch with inputs; auto-issue on failure
- infra/airflow/dags/commodity_price_pipeline.py: 6-task DAG (fetch x3 → validate → upsert → trigger_mtm_recalc)
- Integration tests mock yfinance; DB-touching tests gated behind --run-integration

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push origin main
```

## COWORK HANDOFF

```
=== COWORK HANDOFF — PHASE 4 BEGIN ===

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
  subject: feat(ingestion): Phase 4 — yfinance pipeline + GHA cron + Airflow DAG
  push:    <paste the "To ... main -> main" line>

Validation matrix:
  [✓/✗] 1. mypy strict                   <N source files, 0 errors | N errors>
  [✓/✗] 2. ruff                           <clean | N issues>
  [✓/✗] 3. pytest (unit, no integration)  <N/N passed, M skipped>
  [✓/✗] 4. fetch_prices --dry-run         <3 rows | blocked>
  [✓/✗] 5. DAG import + task count        <6 tasks: [...] | skipped>
  [✓/✗] 6. GHA YAML parses                <ok | error>
  [✓/✗] 7. secrets scan                   <clean | N matches>

Dry-run sample (last 3 ingested prices, if step 4 ran):
  ZS=F        <value> USc/bu   <ts>   YFINANCE_CBOT
  ZC=F        <value> USc/bu   <ts>   CBOT_PROXY_YFINANCE
  USDBRL=X    <value> BRL/USD  <ts>   YFINANCE_FX

Files created:
  backend/app/services/:      price_ingestion.py
  backend/scripts/:           fetch_prices.py
  backend/tests/integration/: test_price_ingestion.py, conftest.py
  infra/airflow/dags/:        commodity_price_pipeline.py
  .github/workflows/:         price_update.yml

Blockers / errors (if ❌):
  <step number>: <last 20 lines of command output>
  hypothesis: <your best guess at cause>
  scope-of-fix: <within prompt scope / requires Diego>

Next expected action (Diego):
  - Push triggers GHA workflow on schedule — wait for next 21:00 UTC and check the Actions tab.
  - Optionally trigger manually: `gh workflow run price_update.yml -f dry_run=true`
  - Optionally boot Airflow locally: `docker compose -f infra/docker-compose.yml up airflow` (after uncommenting the airflow service — NOT required for Phase 4 completion).
  - Return to Cowork for Phase 5 (Position CRUD + Excel import).

Open questions for Diego:
  <list or "none">

=== COWORK HANDOFF — PHASE 4 END ===
```
