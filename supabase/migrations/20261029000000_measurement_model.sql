-- Redesign Phase 1: measurement model (docs/redesign-plan.md §2.1–2.2, §4 "Migration A", profile part).
-- Additive only: existing tables and columns are kept and existing rows stay valid.
-- Enum labels mirror app/pipeline/models.py; tests/integration/test_measurement_schema.py keeps them equal.
-- Rollback: supabase/rollback/20261029000000_measurement_model.down.sql

create type fit_mode          as enum ('quick_fit', 'personal_fit');
create type measurement_basis as enum ('body', 'garment');
create type fit_category      as enum ('bottoms', 'tops', 'dresses', 'outerwear');
create type size_system       as enum ('eu', 'us');
create type quick_size        as enum ('XS', 'S', 'M', 'L', 'XL');

-- ── Measurement catalog ──────────────────────────────────────────────────
-- A lookup table, not an enum, so adding a measurement later is an insert.
create table measurement_dimensions (
  dimension text primary key check (dimension ~ '^[a-z_]+$'),
  label     text not null
);

insert into measurement_dimensions (dimension, label) values
  ('chest',     'Chest / bust'),
  ('waist',     'Waist'),
  ('hips',      'Hips'),
  ('shoulders', 'Shoulders'),
  ('inseam',    'Inseam'),
  ('sleeve',    'Sleeve length'),
  ('height',    'Height');

-- ── Profiles ─────────────────────────────────────────────────────────────
-- The current app only saves exact measurements, so existing and new rows default to Personal Fit.
-- Phase 2 sets the mode explicitly when Quick Fit is introduced.
alter table profiles
  add column fit_mode    fit_mode not null default 'personal_fit',
  add column size_system size_system;

-- Existing rows are body measurements. The primary key stays (user_id, dimension) for now:
-- storing a body and a garment value for the same dimension is a Phase 2 change.
alter table fit_measurements
  add column basis        measurement_basis not null default 'body',
  add column garment_note text check (char_length(garment_note) <= 200),
  add constraint fit_measurements_dimension_fkey
    foreign key (dimension) references measurement_dimensions (dimension);

-- Quick Fit: one standard size per garment category.
create table quick_sizes (
  user_id    uuid references profiles on delete cascade,
  category   fit_category not null,
  size       quick_size not null,
  updated_at timestamptz not null default now(),
  primary key (user_id, category)
);
create trigger quick_sizes_updated_at before update on quick_sizes for each row execute function set_updated_at();

-- Approximate body ranges for standard sizes. Every row names its source; values are seeded once
-- a source table is approved (docs/redesign-plan.md §7).
create table size_references (
  system    size_system not null,
  category  fit_category not null,
  size      quick_size not null,
  dimension text not null references measurement_dimensions,
  min_cm    numeric(5,1) not null,
  max_cm    numeric(5,1) not null,
  source    text not null check (btrim(source) <> ''),
  primary key (system, category, size, dimension),
  check (min_cm < max_cm)
);

-- ── Row-level security and grants ───────────────────────────────────────
alter table measurement_dimensions enable row level security;
alter table quick_sizes            enable row level security;
alter table size_references        enable row level security;

create policy own_rows on quick_sizes for all to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy public_read on measurement_dimensions for select to anon, authenticated using (true);
create policy public_read on size_references        for select to anon, authenticated using (true);

grant select on measurement_dimensions, size_references to anon, authenticated;
grant select, insert, update, delete on quick_sizes to authenticated;
grant select, insert, update, delete on measurement_dimensions, quick_sizes, size_references to service_role;
