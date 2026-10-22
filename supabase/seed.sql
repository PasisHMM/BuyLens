-- Buy Lens: development seed data.
-- Idempotent: safe to run repeatedly (`supabase db reset` runs it automatically).
--
-- IMPORTANT: seller trust ratings and return policies are intentionally left empty
-- ("verified": false). Fill them in from each store's published policy before launch;
-- the Seller Risk card must never show made-up policy details.

insert into brands (name, slug) values
  ('Levi''s',              'levis'),
  ('Everlane',             'everlane'),
  ('Madewell',             'madewell'),
  ('AGOLDE',               'agolde'),
  ('Wrangler',             'wrangler'),
  ('Lee',                  'lee'),
  ('Gap',                  'gap'),
  ('Abercrombie & Fitch',  'abercrombie-fitch'),
  ('J.Crew',               'j-crew'),
  ('Uniqlo',               'uniqlo'),
  ('Zara',                 'zara'),
  ('H&M',                  'h-m'),
  ('Mango',                'mango'),
  ('Citizens of Humanity', 'citizens-of-humanity'),
  ('MOTHER',               'mother'),
  ('FRAME',                'frame'),
  ('RE/DONE',              're-done'),
  ('Good American',        'good-american'),
  ('PAIGE',                'paige'),
  ('7 For All Mankind',    '7-for-all-mankind'),
  ('Ralph Lauren',         'ralph-lauren'),
  ('Banana Republic',      'banana-republic'),
  ('Old Navy',             'old-navy'),
  ('American Eagle',       'american-eagle'),
  ('Free People',          'free-people'),
  ('Reformation',          'reformation'),
  ('Hudson',               'hudson'),
  ('DL1961',               'dl1961'),
  ('Nudie Jeans',          'nudie-jeans'),
  ('G-Star RAW',           'g-star-raw')
on conflict (slug) do update set name = excluded.name;

-- MVP seller allow-list (draft; see "Open decisions" in the plan).
-- adapter = 'jsonld' means the generic schema.org/Product extractor until a dedicated adapter exists.
insert into sellers (name, domain, official_brand, adapter, trust_rating, return_policy) values
  ('Levi''s official store',   'levi.com',      (select id from brands where slug = 'levis'),    'jsonld', null, '{"verified": false}'),
  ('Everlane official store',  'everlane.com',  (select id from brands where slug = 'everlane'), 'jsonld', null, '{"verified": false}'),
  ('Madewell official store',  'madewell.com',  (select id from brands where slug = 'madewell'), 'jsonld', null, '{"verified": false}'),
  ('AGOLDE official store',    'agolde.com',    (select id from brands where slug = 'agolde'),   'jsonld', null, '{"verified": false}'),
  ('Nordstrom',                'nordstrom.com', null,                                            'jsonld', null, '{"verified": false}')
on conflict (domain) do update
  set name = excluded.name,
      official_brand = excluded.official_brand,
      adapter = excluded.adapter;
