-- Undo migrations/20261029000000_measurement_model.sql. Run by hand only; CI never applies this folder.
-- Data loss: Quick Fit sizes, size references, profile fit modes and size systems, and each
-- measurement's basis and garment note are dropped. Exact measurements and everything older are kept.
-- Fails (and changes nothing) if a measurement outside the original waist/inseam/hips set exists,
-- because the old app could not read it: delete or export those rows first.

begin;

do $$
begin
  if exists (select 1 from fit_measurements where dimension not in ('waist', 'inseam', 'hips')) then
    raise exception 'fit_measurements has dimensions the previous schema does not use';
  end if;
end $$;

drop table size_references;
drop table quick_sizes;

alter table fit_measurements
  drop constraint fit_measurements_dimension_fkey,
  drop column garment_note,
  drop column basis;

alter table profiles
  drop column size_system,
  drop column fit_mode;

drop table measurement_dimensions;

drop type quick_size;
drop type size_system;
drop type fit_category;
drop type measurement_basis;
drop type fit_mode;

commit;
