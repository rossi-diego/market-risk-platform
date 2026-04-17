# Phase Prompts — how to run each phase safely

This folder contains paste-ready prompts for Claude Code, one per phase. Each prompt is self-contained: Claude Code reads the file via its `Read` tool (no multi-line paste glitches), executes the tasks, runs mandatory validation, commits + pushes if green, and prints a `COWORK HANDOFF` block at the end.

## The loop

For every phase:

1. **Cowork (Diego)** — paste into Claude Code:
   ```
   Read docs/phase-prompts/phase-<NN>-<title>.md and execute it end-to-end. Bypass mode is active — do not ask for confirmation at any step. Follow the failure path if anything breaks before commit.
   ```
2. **Claude Code** — reads the file, runs tasks 1 through N, runs `MANDATORY validation` 1 through M, commits + pushes if all invariants hold, and prints the `COWORK HANDOFF` block.
3. **Cowork (Diego)** — copies everything between `=== COWORK HANDOFF — PHASE N BEGIN ===` and `=== COWORK HANDOFF — PHASE N END ===` (inclusive), pastes back into the Cowork chat.
4. **Cowork (assistant)** — cross-validates from the mount + remote Git + Supabase MCP, flags anything off, and either greenlights the next phase or debugs.
5. **Diego** — runs the manual checkpoints in the phase's "Next expected action" section (boot servers, smoke-test endpoints, open pages).
6. Move to next phase.

## Validation layers (defense in depth)

Each phase is validated on three levels — any single one failing is enough to block progression.

### Layer 1 — Claude Code self-validation (inside the prompt)

Every phase prompt ends with a `MANDATORY validation` section that lists numbered commands (1, 2, 3, ...) Claude Code MUST run before committing. If any command fails its expected output, Claude Code STOPS, does NOT commit, and prints the handoff block with `Status: ❌` + the failing step's output + a hypothesis.

Typical Layer 1 checks:
- `mypy --strict` → 0 errors
- `ruff check` → clean
- `pytest` → all pass with coverage floor
- Smoke scripts → expected stdout
- No files outside declared scope
- No secrets in tracked content (`git grep` pattern scan)

### Layer 2 — Cowork cross-validation (after handoff paste)

When Diego pastes the handoff back, the Cowork assistant runs independent checks:

- **Git sync**: `git ls-remote origin main` compared to the local HEAD reported in the handoff — must match.
- **File count delta**: diff the handoff's "Files created" list against `git diff --name-only <prev_sha>..<new_sha>` → expected set equals declared set.
- **Secrets sanity**: `git diff <prev_sha>..<new_sha> | grep -iE` for any JWT-shaped string, service role key prefix, etc.
- **Phase-specific sanity**: e.g., Phase 2 reads the Supabase tables via MCP and compares against the ORM; Phase 4 checks that the Actions tab in GitHub has a workflow registered; Phase 6 runs one VaR sanity computation independently and compares to the sample value the handoff reports.

The goal: catch Claude-Code-level lies or partial truths. Rare but possible — ANY agent might report "pytest passed" while skipping a test.

### Layer 3 — Manual checkpoints (Diego, in-browser or CLI)

Every phase has a "Next expected action (Diego)" section. These are things only a human can validate:

- **Phase 1**: `uvicorn` boots, `/api/v1/health` returns 200, `pnpm dev` renders the Next.js welcome page.
- **Phase 2**: Supabase Studio shows RLS green badges on user tables.
- **Phase 3**: Hand-calculator check of one sample price.
- **Phase 4**: GitHub Actions "Run workflow" button works manually.
- **Phase 5**: Swagger UI at `/api/v1/docs`, authenticate, exercise endpoints.
- **Phase 6**: Call `POST /risk/var` manually, cross-check the number against an independent calc.

Layer 3 is the last safety net. Do NOT skip it even when Layers 1 and 2 are green — it's where latent bugs (wrong env, broken deployment, weird browser states) surface.

## What happens on failure

If Layer 1 fails → the phase handoff has `Status: ❌`, no commit exists, branch is unchanged. Diego pastes to Cowork, the assistant reads the failed step + output + hypothesis, proposes a fix. Diego either:
- Paste the fix directly into Claude Code to retry.
- Discuss the fix first in Cowork if the cause isn't clear.

If Layer 2 fails → the commit exists and is pushed, but Cowork flags a discrepancy. Most common: a file that was reported created isn't on the remote (Claude Code built it but didn't `git add` somehow). Recovery: Diego re-runs the phase prompt; Claude Code detects the existing state and fills gaps.

If Layer 3 fails → the code compiles but behaves wrong in practice. Escalate: open a debug session in Cowork using the `engineering:debug` skill, bring the error output + steps to reproduce.

## Cadence expectations (weekend-warrior pace)

Per phase, end-to-end:

- Layer 1 (Claude Code): 5 – 45 min depending on phase size (Phase 10 frontend is the longest).
- Layer 2 (Cowork validation): 1 – 3 min of chat.
- Layer 3 (manual): 2 – 10 min.
- **Total per phase: ~30 min – 1 h of wall clock for most; Phase 10 – 11 are the outliers (~2 h).**

Time you actually spend at the keyboard is even less — Claude Code runs in the background while you watch the handoff scroll by.

## Phases in this folder

| File | Phase | Output | Where most work lives |
|------|-------|--------|-----------------------|
| `phase-01-scaffold.md` | 1 | Repo scaffold (backend + frontend + infra + CI + tooling) | Claude Code |
| `phase-02-backend-models.md` | 2 | SQLAlchemy ORM + Pydantic schemas + Alembic baseline | Claude Code (Supabase side done via Cowork MCP before) |
| `phase-03-domain-core.md` | 3 | Pricing + per-leg exposure + types | Claude Code |
| `phase-04-price-ingestion.md` | 4 | yfinance pipeline + GHA cron + Airflow DAG | Claude Code |
| `phase-05-positions-crud.md` | 5 | FastAPI CRUD + Excel import | Claude Code |
| `phase-06-risk-engine.md` | 6 | VaR (3 methods) + CVaR + stress | Claude Code |

Phases 7 – 13 are generated just-in-time after each preceding phase ships. This is intentional: later phases depend on lessons learned (performance bottlenecks, UX decisions, API shape realities) that only emerge once the earlier phases are live.

## One-liner to start the next phase

```
Read docs/phase-prompts/phase-<NN>-<title>.md and execute it end-to-end. Bypass mode is active — do not ask for confirmation at any step. Follow the failure path if anything breaks before commit.
```
