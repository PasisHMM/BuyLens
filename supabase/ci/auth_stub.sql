-- Minimal stand-in for Supabase's auth schema and roles, so migrations and RLS
-- can be tested against plain PostgreSQL in CI. Never apply this to a Supabase project.

create schema if not exists auth;

create table if not exists auth.users (
  id uuid primary key default gen_random_uuid()
);

do $$
begin
  create role anon nologin;
exception when duplicate_object then null;
end $$;

do $$
begin
  create role authenticated nologin;
exception when duplicate_object then null;
end $$;

do $$
begin
  create role service_role nologin bypassrls;
exception when duplicate_object then null;
end $$;

-- Same contract as Supabase: the user id is the `sub` claim of request.jwt.claims.
create or replace function auth.uid() returns uuid
language sql stable as $$
  select nullif(current_setting('request.jwt.claims', true)::jsonb ->> 'sub', '')::uuid
$$;

grant usage on schema auth to anon, authenticated, service_role;
grant usage on schema public to anon, authenticated, service_role;
