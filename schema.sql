-- Yaadi schema — paste into Supabase SQL editor
-- Run once to create all tables.

create table households (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  created_at timestamptz default now()
);

create table users (
  id uuid primary key default gen_random_uuid(),
  household_id uuid references households(id) on delete cascade,
  phone text unique not null,            -- E.164, e.g. +15105551234
  display_name text not null,
  google_refresh_token text,             -- Phase 3
  google_calendar_id text default 'primary',
  created_at timestamptz default now()
);

create table lists (
  id uuid primary key default gen_random_uuid(),
  household_id uuid references households(id) on delete cascade,
  name text not null,                    -- 'grocery', 'costco', 'reminders'
  created_at timestamptz default now(),
  unique (household_id, name)
);

create table items (
  id uuid primary key default gen_random_uuid(),
  list_id uuid references lists(id) on delete cascade,
  text text not null,
  added_by uuid references users(id),
  done boolean default false,
  created_at timestamptz default now()
);

create table reminders (
  id uuid primary key default gen_random_uuid(),
  household_id uuid references households(id) on delete cascade,
  created_by uuid references users(id),
  text text not null,
  remind_at timestamptz not null,
  sent boolean default false,
  scope text check (scope in ('me','us')) default 'me'
);

create index on items (list_id, done);
create index on reminders (remind_at) where sent = false;

-- ── Seed your household (edit the phone numbers, then run) ──────────────
-- insert into households (id, name) values
--   ('11111111-1111-1111-1111-111111111111', 'Sumedh Home');
--
-- insert into users (household_id, phone, display_name) values
--   ('11111111-1111-1111-1111-111111111111', '+1510XXXXXXX', 'Sumedh'),
--   ('11111111-1111-1111-1111-111111111111', '+1510YYYYYYY', 'Spouse');
--
-- insert into lists (household_id, name) values
--   ('11111111-1111-1111-1111-111111111111', 'grocery'),
--   ('11111111-1111-1111-1111-111111111111', 'costco'),
--   ('11111111-1111-1111-1111-111111111111', 'reminders');
