-- =====================================================================
-- Migration 2/3 — Row Level Security policies
-- Phase 2 of market-risk-platform
-- =====================================================================
-- Enables RLS on every user-scoped table + grants safe read on public tables.
-- Policy pattern:
--   user tables:   auth.uid() = user_id (SELECT, INSERT, UPDATE, DELETE)
--   fixations:     inherited via frame_id → physical_frames.user_id
--   public tables: authenticated users can SELECT; only service role writes.

begin;

-- =====================================================================
-- User-scoped tables: per-row user isolation via auth.uid()
-- =====================================================================

alter table physical_frames enable row level security;

create policy "physical_frames_select_own"
    on physical_frames for select
    using (auth.uid() = user_id);

create policy "physical_frames_insert_own"
    on physical_frames for insert
    with check (auth.uid() = user_id);

create policy "physical_frames_update_own"
    on physical_frames for update
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

create policy "physical_frames_delete_own"
    on physical_frames for delete
    using (auth.uid() = user_id);

-- ---------------------------------------------------------------------

alter table cbot_derivatives enable row level security;

create policy "cbot_derivatives_select_own" on cbot_derivatives for select using (auth.uid() = user_id);
create policy "cbot_derivatives_insert_own" on cbot_derivatives for insert with check (auth.uid() = user_id);
create policy "cbot_derivatives_update_own" on cbot_derivatives for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "cbot_derivatives_delete_own" on cbot_derivatives for delete using (auth.uid() = user_id);

-- ---------------------------------------------------------------------

alter table basis_forwards enable row level security;

create policy "basis_forwards_select_own" on basis_forwards for select using (auth.uid() = user_id);
create policy "basis_forwards_insert_own" on basis_forwards for insert with check (auth.uid() = user_id);
create policy "basis_forwards_update_own" on basis_forwards for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "basis_forwards_delete_own" on basis_forwards for delete using (auth.uid() = user_id);

-- ---------------------------------------------------------------------

alter table fx_derivatives enable row level security;

create policy "fx_derivatives_select_own" on fx_derivatives for select using (auth.uid() = user_id);
create policy "fx_derivatives_insert_own" on fx_derivatives for insert with check (auth.uid() = user_id);
create policy "fx_derivatives_update_own" on fx_derivatives for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "fx_derivatives_delete_own" on fx_derivatives for delete using (auth.uid() = user_id);

-- ---------------------------------------------------------------------

alter table trade_events enable row level security;

create policy "trade_events_select_own" on trade_events for select using (auth.uid() = user_id);
create policy "trade_events_insert_own" on trade_events for insert with check (auth.uid() = user_id);
-- No update/delete on audit log by default (immutable). If maintenance is ever needed, use service role.

-- ---------------------------------------------------------------------

alter table scenarios enable row level security;

create policy "scenarios_select_own" on scenarios for select using (auth.uid() = user_id);
create policy "scenarios_insert_own" on scenarios for insert with check (auth.uid() = user_id);
create policy "scenarios_update_own" on scenarios for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "scenarios_delete_own" on scenarios for delete using (auth.uid() = user_id);

-- =====================================================================
-- Fixations inherit access control from the parent frame
-- =====================================================================

alter table physical_fixations enable row level security;

create policy "physical_fixations_select_via_frame"
    on physical_fixations for select
    using (exists (
        select 1 from physical_frames
        where physical_frames.id = physical_fixations.frame_id
          and physical_frames.user_id = auth.uid()
    ));

create policy "physical_fixations_insert_via_frame"
    on physical_fixations for insert
    with check (exists (
        select 1 from physical_frames
        where physical_frames.id = physical_fixations.frame_id
          and physical_frames.user_id = auth.uid()
    ));

create policy "physical_fixations_update_via_frame"
    on physical_fixations for update
    using (exists (
        select 1 from physical_frames
        where physical_frames.id = physical_fixations.frame_id
          and physical_frames.user_id = auth.uid()
    ))
    with check (exists (
        select 1 from physical_frames
        where physical_frames.id = physical_fixations.frame_id
          and physical_frames.user_id = auth.uid()
    ));

create policy "physical_fixations_delete_via_frame"
    on physical_fixations for delete
    using (exists (
        select 1 from physical_frames
        where physical_frames.id = physical_fixations.frame_id
          and physical_frames.user_id = auth.uid()
    ));

-- =====================================================================
-- Public tables: authenticated users read-only; writes via service role
-- =====================================================================

alter table prices enable row level security;

create policy "prices_select_authenticated"
    on prices for select
    to authenticated
    using (true);

-- INSERT/UPDATE/DELETE on prices: only service role (handled by absence of policy
-- for those actions; Supabase service role bypasses RLS).

-- ---------------------------------------------------------------------

alter table mtm_premiums enable row level security;

create policy "mtm_premiums_select_authenticated"
    on mtm_premiums for select
    to authenticated
    using (true);

create policy "mtm_premiums_update_authenticated"
    on mtm_premiums for update
    to authenticated
    using (true)
    with check (true);

-- ---------------------------------------------------------------------

alter table scenarios_templates enable row level security;

create policy "scenarios_templates_select_authenticated"
    on scenarios_templates for select
    to authenticated
    using (true);

-- Templates are read-only from the application (seeded via migration).

commit;
