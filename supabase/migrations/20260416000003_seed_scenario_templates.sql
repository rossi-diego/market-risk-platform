-- =====================================================================
-- Migration 3/3 — Seed scenarios_templates with 4 historical scenarios
-- Phase 2 of market-risk-platform
-- =====================================================================
-- Source: .claude/skills/risk-engine-patterns/references/stress_scenarios.md
-- Shocks are expressed as decimal fractions (0.35 = +35%, -0.35 = -35%).
-- Basis columns are 0 for the 4 historical built-ins — the dominant shocks
-- were on CBOT flat price and FX, with basis relatively stable.

begin;

insert into scenarios_templates
    (name, description, cbot_soja_shock_pct, cbot_milho_shock_pct,
     basis_soja_shock_pct, basis_milho_shock_pct, fx_shock_pct, source_period)
values
    (
        '2008 GFC',
        'Global Financial Crisis — commodity demand collapse, flight to USD. Severe CBOT drops paired with BRL weakening.',
        -0.35, -0.42, 0, 0, 0.40,
        'Sep–Dec 2008'
    ),
    (
        '2012 US Drought',
        'US Midwest drought — severe CBOT rally, especially corn. Moderate BRL weakening.',
         0.35,  0.45, 0, 0,  0.08,
        'Jun–Aug 2012'
    ),
    (
        '2020 COVID',
        'COVID-19 market shock — risk-off flight to USD, moderate CBOT drop, BRL collapse.',
        -0.12, -0.18, 0, 0,  0.35,
        'Mar 2020'
    ),
    (
        '2022 Ukraine War',
        'Russia–Ukraine war — grain supply shock, CBOT rally. Modest BRL strengthening as commodity currencies rallied.',
         0.25,  0.30, 0, 0, -0.05,
        'Feb–May 2022'
    )
on conflict (name) do update set
    description = excluded.description,
    cbot_soja_shock_pct = excluded.cbot_soja_shock_pct,
    cbot_milho_shock_pct = excluded.cbot_milho_shock_pct,
    basis_soja_shock_pct = excluded.basis_soja_shock_pct,
    basis_milho_shock_pct = excluded.basis_milho_shock_pct,
    fx_shock_pct = excluded.fx_shock_pct,
    source_period = excluded.source_period;

commit;
