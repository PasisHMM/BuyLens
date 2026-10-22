-- Buy Lens: Phase 2 (analyzer engine).

-- The check worker writes catalog rows and run results as service_role, which bypasses RLS.
-- Supabase grants these by default; stating them keeps plain-Postgres CI identical.
grant usage on schema public to service_role;
grant select, insert, update, delete on all tables in schema public to service_role;
alter default privileges in schema public grant select, insert, update, delete on tables to service_role;

-- Product image for the results header and the "A recent check" card.
alter table products add column image_url text;

-- Seller-specific product identity, and the full parsed listing so later checks can reuse it
-- as a comparable without re-fetching (until it is older than the listing cache TTL).
alter table listings add column external_id text;
alter table listings add column extract jsonb;

-- Shipping as shown on the page, before we know the user's location (null = unknown).
comment on column listings.shipping_cents is 'null = unknown; never treated as free';

-- Curated shipping rules per seller: {"verified": bool, "free_over_cents": int, "flat_cents": int}.
-- Used only when the product page does not state shipping; unverified rules are ignored.
alter table sellers add column shipping_policy jsonb not null default '{"verified": false}';

-- Fast lookup of a seller's listing for the same product.
create unique index listings_product_seller_idx on listings (product_id, seller_id);

-- Cached product lookups by identifiers.
create index products_gtin_idx on products (gtin) where gtin is not null;

-- Fix: `unique nulls not distinct (brand_id, mpn)` treated every brand-less, MPN-less product
-- as the same product. Only enforce uniqueness when an MPN is known.
alter table products drop constraint products_brand_id_mpn_key;
create unique index products_brand_mpn_idx on products (brand_id, mpn) where mpn is not null;
