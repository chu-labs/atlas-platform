-- ATLAS platform schema. Applied by `python -m atlas.db migrate`.
create table if not exists schema_migrations (
  version text primary key,
  applied_at timestamptz not null default now()
);

create table if not exists brokers (
  id serial primary key,
  name text not null,
  state text not null
);

create table if not exists buildings (
  id serial primary key,
  plan_number text not null unique,
  name text not null,
  suburb text not null,
  state text not null,
  postcode text not null,
  lat double precision not null default 0,
  lng double precision not null default 0,
  year_built int not null,
  floors int not null,
  lots int not null,
  construction_type text not null,
  roof_type text not null,
  sprinklers boolean not null default false,
  flood_zone text not null default 'none',
  bushfire_bal text not null default 'none',
  distance_to_coast_km double precision not null default 50,
  cladding_flag boolean not null default false,
  last_inspection date
);

create table if not exists policies (
  id serial primary key,
  policy_number text not null unique,
  building_id int not null references buildings(id),
  broker_id int not null references brokers(id),
  product text not null,
  inception_date date not null,
  expiry_date date not null,
  sum_insured numeric(14,2) not null,
  base_premium numeric(12,2) not null,
  excess numeric(10,2) not null default 1000,
  status text not null default 'active'
);
create index if not exists policies_expiry_idx on policies(expiry_date) where status = 'active';
create index if not exists policies_building_idx on policies(building_id);

create table if not exists claims (
  id serial primary key,
  claim_number text not null unique,
  policy_id int not null references policies(id),
  building_id int not null references buildings(id),
  loss_date date not null,
  reported_date date not null,
  peril text not null,
  status text not null,
  incurred numeric(12,2) not null default 0,
  paid numeric(12,2) not null default 0,
  description text not null default ''
);
create index if not exists claims_building_idx on claims(building_id);
create index if not exists claims_policy_idx on claims(policy_id);

create table if not exists renewal_quotes (
  id serial primary key,
  policy_id int not null references policies(id),
  quoted_at timestamptz not null default now(),
  annual_premium numeric(12,2) not null,
  factors jsonb not null default '{}'::jsonb
);

create table if not exists ai_reports (
  id serial primary key,
  kind text not null,
  subject_key text not null,
  model text not null,
  created_at timestamptz not null default now(),
  input_tokens int not null default 0,
  output_tokens int not null default 0,
  content text not null
);
create index if not exists ai_reports_subject_idx on ai_reports(kind, subject_key, created_at desc);
