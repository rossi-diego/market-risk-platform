-- =====================================================================
-- Migration 4/4 — Advisor polish (security + performance)
-- Phase 2 of market-risk-platform
-- =====================================================================
-- Fixes:
--   - function_search_path_mutable on set_updated_at (security hardening)
--   - 26× auth_rls_initplan (RLS policies re-evaluating auth.uid() per row)
-- Leaves:
--   - rls_policy_always_true on mtm_premiums_update_authenticated (intentional
--     for MVP; backend will gate via service role in later phases)

begin;

-- 1. Pin search_path on trigger function
create or replace function set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

-- 2. Rewrite all user-table RLS policies to use (select auth.uid())
--    instead of auth.uid() for better query plans at scale.

-- physical_frames
drop policy "physical_frames_select_own" on physical_frames;
drop policy "physical_frames_insert_own" on physical_frames;
drop policy "physical_frames_update_own" on physical_frames;
drop policy "physical_frames_delete_own" on physical_frames;

create policy "physical_frames_select_own" on physical_frames for select using ((select auth.uid()) = user_id);
create policy "physical_frames_insert_own" on physical_frames for insert with check ((select auth.uid()) = user_id);
create policy "physical_frames_update_own" on physical_frames for update using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "physical_frames_delete_own" on physical_frames for delete using ((select auth.uid()) = user_id);

-- cbot_derivatives
drop policy "cbot_derivatives_select_own" on cbot_derivatives;
drop policy "cbot_derivatives_insert_own" on cbot_derivatives;
drop policy "cbot_derivatives_update_own" on cbot_derivatives;
drop policy "cbot_derivatives_delete_own" on cbot_derivatives;

create policy "cbot_derivatives_select_own" on cbot_derivatives for select using ((select auth.uid()) = user_id);
create policy "cbot_derivatives_insert_own" on cbot_derivatives for insert with check ((select auth.uid()) = user_id);
create policy "cbot_derivatives_update_own" on cbot_derivatives for update using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "cbot_derivatives_delete_own" on cbot_derivatives for delete using ((select auth.uid()) = user_id);

-- basis_forwards
drop policy "basis_forwards_select_own" on basis_forwards;
drop policy "basis_forwards_insert_own" on basis_forwards;
drop policy "basis_forwards_update_own" on basis_forwards;
drop policy "basis_forwards_delete_own" on basis_forwards;

create policy "basis_forwards_select_own" on basis_forwards for select using ((select auth.uid()) = user_id);
create policy "basis_forwards_insert_own" on basis_forwards for insert with check ((select auth.uid()) = user_id);
create policy "basis_forwards_update_own" on basis_forwards for update using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "basis_forwards_delete_own" on basis_forwards for delete using ((select auth.uid()) = user_id);

-- fx_derivatives
drop policy "fx_derivatives_select_own" on fx_derivatives;
drop policy "fx_derivatives_insert_own" on fx_derivatives;
drop policy "fx_derivatives_update_own" on fx_derivatives;
drop policy "fx_derivatives_delete_own" on fx_derivatives;

create policy "fx_derivatives_select_own" on fx_derivatives for select using ((select auth.uid()) = user_id);
create policy "fx_derivatives_insert_own" on fx_derivatives for insert with check ((select auth.uid()) = user_id);
create policy "fx_derivatives_update_own" on fx_derivatives for update using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "fx_derivatives_delete_own" on fx_derivatives for delete using ((select auth.uid()) = user_id);

-- trade_events
drop policy "trade_events_select_own" on trade_events;
drop policy "trade_events_insert_own" on trade_events;

create policy "trade_events_select_own" on trade_events for select using ((select auth.uid()) = user_id);
create policy "trade_events_insert_own" on trade_events for insert with check ((select auth.uid()) = user_id);

-- scenarios
drop policy "scenarios_select_own" on scenarios;
drop policy "scenarios_insert_own" on scenarios;
drop policy "scenarios_update_own" on scenarios;
drop policy "scenarios_delete_own" on scenarios;

create policy "scenarios_select_own" on scenarios for select using ((select auth.uid()) = user_id);
create policy "scenarios_insert_own" on scenarios for insert with check ((select auth.uid()) = user_id);
create policy "scenarios_update_own" on scenarios for update using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "scenarios_delete_own" on scenarios for delete using ((select auth.uid()) = user_id);

-- physical_fixations (inherits access via frame)
drop policy "physical_fixations_select_via_frame" on physical_fixations;
drop policy "physical_fixations_insert_via_frame" on physical_fixations;
drop policy "physical_fixations_update_via_frame" on physical_fixations;
drop policy "physical_fixations_delete_via_frame" on physical_fixations;

create policy "physical_fixations_select_via_frame" on physical_fixations for select
    using (exists (
        select 1 from physical_frames
        where physical_frames.id = physical_fixations.frame_id
          and physical_frames.user_id = (select auth.uid())
    ));
create policy "physical_fixations_insert_via_frame" on physical_fixations for insert
    with check (exists (
        select 1 from physical_frames
        where physical_frames.id = physical_fixations.frame_id
          and physical_frames.user_id = (select auth.uid())
    ));
create policy "physical_fixations_update_via_frame" on physical_fixations for update
    using (exists (
        select 1 from physical_frames
        where physical_frames.id = physical_fixations.frame_id
          and physical_frames.user_id = (select auth.uid())
    ))
    with check (exists (
        select 1 from physical_frames
        where physical_frames.id = physical_fixations.frame_id
          and physical_frames.user_id = (select auth.uid())
    ));
create policy "physical_fixations_delete_via_frame" on physical_fixations for delete
    using (exists (
        select 1 from physical_frames
        where physical_frames.id = physical_fixations.frame_id
          and physical_frames.user_id = (select auth.uid())
    ));

commit;
