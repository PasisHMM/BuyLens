-- Redesign Phase 3: every option of a check is stored, including mismatches hidden from the visible list.
-- The rank limit of 3 would drop results, and the old score is no longer calculated.
-- The verdict columns stay, unwritten, until Migration B (docs/redesign-plan.md §4).
-- Rollback: supabase/rollback/20261105000000_results_keep_all_options.down.sql

alter table check_options drop constraint check_options_rank_check;
alter table check_options add constraint check_options_rank_check check (rank >= 1);
alter table check_options alter column score drop not null;
