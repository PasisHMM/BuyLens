-- Buy Lens: initial schema (Phase 1).
-- Conventions: measurements in centimeters (numeric(5,1)), money in integer cents,
-- every user-owned table protected by row-level security keyed on auth.uid().

-- ── Enums ───────────────────────────────────────────────────────────────
create type unit_pref    as enum ('in', 'cm');
create type verdict      as enum ('BUY', 'CONSIDER', 'SKIP');
create type run_status   as enum ('queued', 'running', 'done', 'failed', 'cancelled');
create type check_step   as enum ('product', 'prices', 'fit', 'seller');
create type fit_outcome  as enum ('too_tight', 'fits_well', 'too_loose');
create type skip_reason  as enum ('price', 'fit_concern', 'seller_risk');

-- ── Helpers ─────────────────────────────────────────────────────────────
create function set_updated_at() returns trigger
language plpgsql as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

-- ── User profile ────────────────────────────────────────────────────────
create table profiles (
  user_id     uuid primary key references auth.users on delete cascade,
  unit        unit_pref not null default 'in',
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

-- One row per dimension, so new dimensions (chest, shoulder, rise) need no migration.
create table fit_measurements (
  user_id     uuid references profiles on delete cascade,
  dimension   text not null check (dimension ~ '^[a-z_]+$'),
  value_cm    numeric(5,1) not null check (value_cm between 20 and 250),
  updated_at  timestamptz not null default now(),
  primary key (user_id, dimension)
);

create table brands (
  id    uuid primary key default gen_random_uuid(),
  name  text not null,
  slug  text not null unique
);

create table brand_preferences (
  user_id   uuid references profiles on delete cascade,
  brand_id  uuid references brands on delete cascade,
  primary key (user_id, brand_id)
);

-- ── Catalog ─────────────────────────────────────────────────────────────
create table sellers (
  id              uuid primary key default gen_random_uuid(),
  name            text not null,
  domain          text not null unique,
  official_brand  uuid references brands,
  adapter         text not null,
  trust_rating    numeric(2,1) check (trust_rating between 0 and 5),
  return_policy   jsonb not null default '{}',
  enabled         boolean not null default true
);

create table products (
  id          uuid primary key default gen_random_uuid(),
  brand_id    uuid references brands,
  name        text not null,
  category    text not null,
  gtin        text,
  mpn         text,
  attributes  jsonb not null default '{}',
  unique nulls not distinct (brand_id, mpn)
);

create table listings (
  id              uuid primary key default gen_random_uuid(),
  product_id      uuid references products on delete cascade,
  seller_id       uuid references sellers,
  url             text not null,
  canonical_url   text not null unique,
  currency        char(3) not null default 'USD',
  price_cents     integer not null check (price_cents >= 0),
  shipping_cents  integer check (shipping_cents >= 0),   -- null = unknown, never "free"
  in_stock        boolean,
  sizes           jsonb not null default '[]',
  size_chart      jsonb,
  review_rating   numeric(2,1) check (review_rating between 0 and 5),
  review_count    integer check (review_count >= 0),
  snapshot_key    text,
  fetched_at      timestamptz not null default now()
);
create index listings_product_id_idx on listings (product_id);

create table review_summaries (
  listing_id  uuid primary key references listings on delete cascade,
  summary     jsonb not null,
  model       text not null,
  created_at  timestamptz not null default now()
);

-- ── Verdict runs ────────────────────────────────────────────────────────
create table check_runs (
  id                uuid primary key default gen_random_uuid(),
  user_id           uuid not null references profiles on delete cascade,
  input_url         text not null,
  product_id        uuid references products,
  status            run_status not null default 'queued',
  current_step      check_step,
  selected_size     text,
  profile_snapshot  jsonb not null,
  memory_snapshot   jsonb not null default '{}',
  verdict           verdict,
  headline          text,
  explanation       text,
  why_not           jsonb,
  pipeline_version  text not null,
  error             text,
  created_at        timestamptz not null default now(),
  completed_at      timestamptz
);
create index check_runs_user_recent_idx on check_runs (user_id, created_at desc);

create table check_options (
  id           uuid primary key default gen_random_uuid(),
  run_id       uuid not null references check_runs on delete cascade,
  rank         smallint not null check (rank between 1 and 3),
  listing_id   uuid not null references listings,
  total_cents  integer not null,
  score        numeric(5,4) not null,
  summary      text not null,
  price_check  jsonb not null,
  fit_check    jsonb not null,
  seller_risk  jsonb not null,
  unique (run_id, rank)
);

-- ── Feedback & memory ───────────────────────────────────────────────────
create table feedback (
  id             uuid primary key default gen_random_uuid(),
  run_id         uuid not null references check_runs on delete cascade,
  option_id      uuid references check_options,
  user_id        uuid not null references profiles on delete cascade,
  purchased      boolean not null,
  fit            fit_outcome,
  fit_dimension  text,
  reasons        skip_reason[] not null default '{}',
  note           text,
  applied_delta  jsonb,            -- memory change applied, so an edited answer can be reversed
  created_at     timestamptz not null default now(),
  unique (run_id, user_id)
);

create table fit_memory (
  user_id         uuid references profiles on delete cascade,
  brand_id        uuid references brands,
  category        text not null,
  dimension       text not null,
  ease_adjust_cm  numeric(4,1) not null default 0,
  reference       jsonb,
  evidence_count  integer not null default 1,
  updated_at      timestamptz not null default now(),
  unique nulls not distinct (user_id, brand_id, category, dimension)
);

create table decision_memory (
  user_id            uuid primary key references profiles on delete cascade,
  price_sensitivity  numeric(3,2) not null default 0.50 check (price_sensitivity between 0 and 1),
  risk_aversion      numeric(3,2) not null default 0.50 check (risk_aversion between 0 and 1),
  fit_strictness     numeric(3,2) not null default 0.50 check (fit_strictness between 0 and 1),
  updated_at         timestamptz not null default now()
);

-- ── updated_at triggers ─────────────────────────────────────────────────
create trigger profiles_updated_at         before update on profiles         for each row execute function set_updated_at();
create trigger fit_measurements_updated_at before update on fit_measurements for each row execute function set_updated_at();
create trigger fit_memory_updated_at       before update on fit_memory       for each row execute function set_updated_at();
create trigger decision_memory_updated_at  before update on decision_memory  for each row execute function set_updated_at();

-- ── Row-level security ──────────────────────────────────────────────────
-- (select auth.uid()) is evaluated once per statement instead of once per row.

alter table profiles          enable row level security;
alter table fit_measurements  enable row level security;
alter table brand_preferences enable row level security;
alter table check_runs        enable row level security;
alter table check_options     enable row level security;
alter table feedback          enable row level security;
alter table fit_memory        enable row level security;
alter table decision_memory   enable row level security;
alter table brands            enable row level security;
alter table sellers           enable row level security;
alter table products          enable row level security;
alter table listings          enable row level security;
alter table review_summaries  enable row level security;

create policy own_rows on profiles          for all to authenticated using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy own_rows on fit_measurements  for all to authenticated using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy own_rows on brand_preferences for all to authenticated using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy own_rows on check_runs        for all to authenticated using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy own_rows on feedback          for all to authenticated using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy own_rows on fit_memory        for all to authenticated using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy own_rows on decision_memory   for all to authenticated using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));

-- Options are written by the worker (service role); users may only read options of their own runs.
create policy own_run_options on check_options for select to authenticated
  using (exists (select 1 from check_runs r where r.id = run_id and r.user_id = (select auth.uid())));

-- Catalog: readable by everyone, writable only by the service role (which bypasses RLS).
create policy public_read on brands           for select to anon, authenticated using (true);
create policy public_read on sellers          for select to anon, authenticated using (enabled);
create policy public_read on products         for select to anon, authenticated using (true);
create policy public_read on listings         for select to anon, authenticated using (true);
create policy public_read on review_summaries for select to anon, authenticated using (true);

-- ── Grants (explicit, so the schema also works outside Supabase's default privileges) ──
grant select on brands, sellers, products, listings, review_summaries to anon, authenticated;
grant select, insert, update, delete
  on profiles, fit_measurements, brand_preferences, check_runs, feedback, fit_memory, decision_memory
  to authenticated;
grant select on check_options to authenticated;
