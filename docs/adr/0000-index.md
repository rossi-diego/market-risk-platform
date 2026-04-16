# Architecture Decision Records

Numbered, append-only log of architectural decisions for the market-risk-platform. Each ADR follows the Nygard template (Context, Decision, Options Considered, Trade-off Analysis, Consequences, Action Items).

New ADRs are created when a decision meaningfully shapes the system's structure, interfaces, or non-functional behavior. Decisions that are easily reversible or scope-local don't warrant an ADR.

## Status legend

- **Proposed** — under discussion, not yet implemented.
- **Accepted** — in force; the codebase reflects this decision.
- **Deprecated** — still true of the current code, but a superseding decision is being drafted.
- **Superseded by ADR-NNNN** — replaced by a newer decision; kept for historical record.

## Index

| # | Title | Status | Date |
|---|-------|--------|------|
| [0001](./0001-instrument-model.md) | Four-table instrument model | Accepted | 2026-04-16 |
| [0002](./0002-fixacao-model.md) | Physical contract model — Frame + Fixações (parent–child) | Accepted | 2026-04-16 |
| [0003](./0003-risk-aggregation.md) | Risk aggregation — flat and per-leg VaR methodology | Accepted | 2026-04-16 |

## How to add an ADR

1. Copy an existing file as a template; use the next free number (zero-padded, 4 digits).
2. Follow the section structure: **Status**, **Date**, **Deciders**, **Context**, **Decision**, **Options Considered**, **Trade-off Analysis**, **Consequences**, **Action Items**.
3. Update this index with the new row.
4. Commit under a message like `docs(adr): NNNN <title>`.

## Related

- `CLAUDE.md` — project-level instructions; every accepted ADR should be reflected in the relevant sections.
- `docs/BUILD_PLAN.md` — phased delivery plan; ADR action items link to specific phases.
- `.claude/skills/risk-engine-patterns/SKILL.md` — domain-specific knowledge reinforced by ADR-0003.
- `.claude/skills/commodity-price-decomposition/SKILL.md` — price model underpinning ADR-0001 and ADR-0002.
