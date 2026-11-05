-- Rollback of 20261105000000_results_keep_all_options.sql.
-- Refuses to run while rows exist that the old constraints would reject, so nothing is lost silently.

do $$
begin
  if exists (select 1 from check_options where rank > 3 or score is null) then
    raise exception 'check_options holds rows the old constraints reject; export or remove them first';
  end if;
end $$;

alter table check_options drop constraint check_options_rank_check;
alter table check_options add constraint check_options_rank_check check (rank between 1 and 3);
alter table check_options alter column score set not null;
