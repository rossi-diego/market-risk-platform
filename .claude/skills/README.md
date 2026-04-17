# .claude/skills — project-specific skills

Four skills scoped to the **market-risk-platform** repo. They encode domain knowledge (price formation, risk methodology, Supabase + FastAPI integration, Airflow DAG) that isn't derivable from reading the code alone.

## How they load

| Tool          | Mechanism                                                                 |
|---------------|---------------------------------------------------------------------------|
| Claude Code   | Auto-loaded from `.claude/skills/<name>/SKILL.md` when the repo is open. |
| Cowork chat   | Install `../market-risk-platform.plugin` once (Settings → Plugins).       |

Both paths read the same `SKILL.md` files in this folder — single source of truth.

## The skills

### `commodity-price-decomposition`
Price formation model for soja / milho and the CBOT / FX / Premium delta decomposition.

**Triggers on:** BRL/ton formula, USc/bu → BRL/ton conversions, unit conversion factors (36.744 / 56.0), `ZS=F` / `ZC=F` / `USDBRL=X`, why milho uses `ZC=F` as proxy, `price_source` enum flags, MTM premium vs trade premium, per-position exposure breakdown.

**Keeps you from:** inlining conversion math outside `risk/pricing.py`, forgetting the `CBOT_PROXY_YFINANCE` flag, mixing trade premium with MTM premium.

### `risk-engine-patterns`
Production patterns for the `backend/app/risk/` module.

**Triggers on:** VaR (historical / parametric / Monte Carlo), CVaR / Expected Shortfall, stress testing (historical + hypothetical), seed-controlled MC, P&L attribution, Basel III/IV, FRTB, Jorion, Hull, √10 scaling, confidence levels 95 / 99 / 97.5 %.

**Keeps you from:** non-reproducible randomness (missing `np.random.seed`), inconsistent confidence levels, stress scenarios without literature citations, untyped risk outputs.

Includes: `references/stress_scenarios.md` — the hard-coded historical shock table (2008 GFC, 2012 drought, 2020 COVID, 2022 Ukraine).

### `supabase-fastapi-async`
FastAPI ↔ Supabase integration patterns.

**Triggers on:** Supabase client setup, async SQLAlchemy 2.0 sessions, RLS policies, Storage bucket access for Excel/CSV upload, Auth JWT validation, upsert patterns, anon key vs service role key, testing Supabase-backed endpoints, migration tracking with Alembic-on-Supabase.

**Keeps you from:** leaking the service role key to the frontend, missing RLS on new tables, synchronous DB calls in async handlers.

### `airflow-price-pipeline`
The `commodity_price_pipeline` DAG.

**Triggers on:** DAG authoring (`fetch_soy → fetch_corn → fetch_fx → validate → upsert_supabase → trigger_mtm_recalc`), local Airflow via Docker Compose, testing DAGs, Supabase connection configuration, scheduling at 18:00 BRT, comparison with the GitHub Actions cron that serves the same purpose in the demo deployment.

**Keeps you from:** diverging the Airflow DAG from the GitHub Actions workflow, forgetting the `trigger_mtm_recalc` downstream step, hardcoding Supabase credentials in the DAG.

## Adding a new skill

1. Create `./<new-skill-name>/SKILL.md` with YAML frontmatter:

   ```yaml
   ---
   name: <new-skill-name>
   description: >
     One paragraph describing when the skill should trigger. Be specific about
     keywords and scenarios — the description is what the LLM uses to decide.
   ---
   ```

2. Write the body in standard Markdown. Keep it action-oriented (patterns to apply, anti-patterns to avoid, references).

3. Optionally add `./<new-skill-name>/references/*.md` for larger reference material the SKILL.md can point to but shouldn't inline.

4. Rebuild the Cowork plugin bundle:

   ```bash
   # from repo root
   cd .claude && rm -f market-risk-platform.plugin
   python -c "
   import zipfile, pathlib
   root = pathlib.Path('skills').parent
   with zipfile.ZipFile('market-risk-platform.plugin', 'w', zipfile.ZIP_DEFLATED) as zf:
       for p in root.rglob('*'):
           if p.is_file() and '_archive' not in p.parts and p.suffix != '.plugin':
               zf.write(p, p.relative_to(root))
   "
   ```

   Then reinstall the `.plugin` in Cowork.

## What's in `_archive/`

The original `.skill` ZIP bundles before they were extracted. Kept for reference; git-ignored — rebuild them from the source directories if you need redistribution.
