# Claude Configuration — commodity-risk-dashboard

Complete guide to install all skills, knowledge base, and MCP configuration
for working on this project with Claude.

---

## 1. Install Skills (4 skills)

Skills teach Claude the project-specific patterns so you don't repeat context.
Install via **Claude.ai → Settings → Skills → Install from file (.skill)**.

| File | What it does |
|---|---|
| `commodity-price-decomposition.skill` | BRL/ton formula, unit conversions, decomposition, yfinance tickers, PriceSource enum |
| `risk-engine-patterns.skill` | VaR (3 methods), CVaR/ES, stress test patterns, typed outputs, test requirements |
| `supabase-fastapi-async.skill` | FastAPI + Supabase integration, RLS, JWT auth, upsert, Storage uploads |
| `airflow-price-pipeline.skill` | DAG structure, task implementations, Docker Compose setup, GH Actions cron |

**Install order:** install all 4, order doesn't matter.

---

## 2. Add Knowledge Base Documents (4 documents)

KB documents give Claude always-on context for domain knowledge.
Add via **Claude.ai → Projects → [this project] → Add to knowledge**.

| File | What it covers |
|---|---|
| `kb/RISK_METHODOLOGY.md` | VaR/CVaR formulas with full literature references, stress test rationale, unit conventions |
| `kb/IMPORT_SCHEMA.md` | Excel/CSV import column definitions, Pydantic validation rules, error response format |
| `kb/DATABASE_SCHEMA.md` | Full Supabase schema: all tables, RLS policies, indexes, storage buckets |
| `CLAUDE.md` (root) | Project overview, price formation model, stack decisions, repo structure, conventions |

**Important:** `CLAUDE.md` belongs in the **repo root** (committed to git) AND as a KB document
in the Claude project. The repo version is for any dev working on the project;
the KB version is for Claude to have it in context automatically.

---

## 3. Connect MCP Servers

Go to **Claude.ai → Settings → Integrations** and verify these are connected:

### Already available — enable and use:

| MCP | Usage in this project |
|---|---|
| **Supabase** | Create/modify tables directly in conversation, run SQL for debugging, inspect schema, validate data after price updates |
| **Vercel** | Deploy frontend, check build logs, manage environment variables |

### Investigate before using:

| MCP | What to check |
|---|---|
| **LSEG** | You have this connected. Check if their API covers B3 CCM (milho futures). If yes, this eliminates the ZC=F proxy and makes the milho price production-grade. Run: "search for CCM or B3 corn futures in LSEG MCP" |

### Not yet connected — worth adding:

| MCP | Where to get it | Why |
|---|---|---|
| **GitHub** | github.com/settings/apps → Claude | Review PRs, check GH Actions cron job results, manage secrets |

---

## 4. Recommended Claude Project Settings

When working inside the Claude Project for this repo:

**Project instructions to add:**
```
This is the commodity-risk-dashboard project. Always follow the price
formation model from CLAUDE.md — never approximate unit conversions inline.
Default to the risk/ module patterns from the risk-engine-patterns skill.
All Supabase operations use the supabase-fastapi-async skill patterns.
Use the Supabase MCP to inspect live schema when writing migrations.
```

---

## 5. Daily Workflow

### Starting a new feature

```
1. Claude opens with CLAUDE.md + KB docs in context (automatic, via Project)
2. Skills trigger automatically when you ask about prices, VaR, Supabase, or Airflow
3. Use Supabase MCP directly: "check the prices table for today's records"
4. Use Vercel MCP for deploy: "deploy frontend to Vercel"
```

### Debugging price data

```
Claude (via Supabase MCP):
"SELECT feed_name, price_date, close_price, price_source
 FROM prices
 ORDER BY price_date DESC
 LIMIT 10"
```

### Writing a new risk metric

```
Prompt: "implement 10-day parametric VaR for a multi-position portfolio"
→ risk-engine-patterns skill triggers automatically
→ Claude uses the typed output pattern (VaRResult dataclass)
→ Claude cites correct literature references
→ Claude includes the normality warning
```

### Importing positions

```
Prompt: "write the ingestion logic for the position import endpoint"
→ supabase-fastapi-async skill triggers (Storage upload pattern)
→ IMPORT_SCHEMA KB provides exact column names and validation rules
→ Claude generates code with correct Pydantic schema
```

---

## 6. File Locations Summary

```
commodity-risk-dashboard/         ← repo root
├── CLAUDE.md                     ← committed to git + added to Claude KB
│
dist/                             ← not in repo, install these in Claude.ai
├── commodity-price-decomposition.skill
├── risk-engine-patterns.skill
├── supabase-fastapi-async.skill
└── airflow-price-pipeline.skill

kb/                               ← add these to Claude Project KB
├── RISK_METHODOLOGY.md
├── IMPORT_SCHEMA.md
└── DATABASE_SCHEMA.md
```

---

## 7. Updating Skills

When project conventions change (new risk metric, updated schema, etc.):

1. Edit the relevant `SKILL.md` in `commodity-skills/skills/<name>/`
2. Re-run from the `skill-creator` directory:
   ```bash
   cd /path/to/mnt/skills/examples/skill-creator
   python3 -m scripts.package_skill \
     /path/to/commodity-skills/skills/<skill-name> \
     /path/to/commodity-skills/dist
   ```
3. Re-install the updated `.skill` file in Claude.ai Settings
4. For KB docs: edit the `.md` file and re-upload to the Claude Project
