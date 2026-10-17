-- =====================================================================
-- Agent Factory: Supabase schema (multi-tenant, RLS enabled)
-- Run in Supabase SQL Editor (or `supabase db push`).
-- =====================================================================

create extension if not exists "pgcrypto";

-- ---------- Tenancy ----------------------------------------------------
create table if not exists tenants (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  plan text not null default 'starter',
  created_at timestamptz not null default now()
);

create table if not exists tenant_members (
  tenant_id uuid not null references tenants(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null default 'member' check (role in ('owner','admin','member')),
  primary key (tenant_id, user_id)
);

-- API keys used by n8n / external systems to call the FastAPI service.
-- Only the SHA-256 hash is stored.
create table if not exists api_keys (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  name text not null,
  key_hash text not null unique,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  last_used_at timestamptz
);

-- Helper: tenants the current logged-in user belongs to
create or replace function public.my_tenants()
returns setof uuid
language sql stable security definer set search_path = public as $$
  select tenant_id from tenant_members where user_id = auth.uid();
$$;

-- ---------- Agents & workflow runs ------------------------------------
create table if not exists agents (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  name text not null,
  kind text not null check (kind in ('research','summarizer','analytics')),
  system_prompt text,
  model text,
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  unique (tenant_id, name)
);

create table if not exists workflow_runs (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  workflow text not null,                       -- e.g. 'daily_factory_report'
  status text not null default 'running'
    check (status in ('running','succeeded','failed')),
  input jsonb not null default '{}'::jsonb,
  output jsonb,
  error text,
  triggered_by text not null default 'api',     -- 'n8n' | 'api' | 'schedule'
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  latency_ms integer
);
create index if not exists idx_runs_tenant_started on workflow_runs (tenant_id, started_at desc);

create table if not exists agent_tasks (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references workflow_runs(id) on delete cascade,
  tenant_id uuid not null references tenants(id) on delete cascade,
  agent_kind text not null,
  step integer not null,
  input jsonb,
  output jsonb,
  status text not null default 'running'
    check (status in ('running','succeeded','failed')),
  tokens_in integer,
  tokens_out integer,
  latency_ms integer,
  created_at timestamptz not null default now()
);
create index if not exists idx_tasks_run on agent_tasks (run_id, step);

-- Persistent memory shared across task cycles / agents
create table if not exists agent_memory (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  scope text not null,                          -- e.g. 'factory:plant-1'
  key text not null,
  value jsonb not null,
  updated_at timestamptz not null default now(),
  unique (tenant_id, scope, key)
);

-- Output quality scores (also mirrored to MLflow)
create table if not exists quality_scores (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references workflow_runs(id) on delete cascade,
  tenant_id uuid not null references tenants(id) on delete cascade,
  metric text not null,
  score numeric not null,
  created_at timestamptz not null default now()
);

-- ---------- Knowledge (SOPs, manuals) for LlamaIndex -------------------
create table if not exists documents (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  title text not null,
  content text not null,
  created_at timestamptz not null default now()
);

-- ---------- Factory domain data ---------------------------------------
create table if not exists factory_lines (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  plant text not null,
  line_name text not null,
  product text,
  target_units_per_shift integer not null default 1000,
  unique (tenant_id, plant, line_name)
);

create table if not exists production_metrics (
  id bigint generated always as identity primary key,
  tenant_id uuid not null references tenants(id) on delete cascade,
  line_id uuid not null references factory_lines(id) on delete cascade,
  shift_date date not null,
  shift text not null check (shift in ('A','B','C')),
  units_produced integer not null,
  units_defective integer not null default 0,
  downtime_minutes integer not null default 0,
  downtime_reason text,
  created_at timestamptz not null default now(),
  unique (line_id, shift_date, shift)
);
create index if not exists idx_metrics_tenant_date on production_metrics (tenant_id, shift_date desc);

-- Generated reports (output of the daily workflow)
create table if not exists reports (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  run_id uuid references workflow_runs(id) on delete set null,
  kind text not null,                           -- 'daily_factory_report' | 'research'
  title text not null,
  body_markdown text not null,
  created_at timestamptz not null default now()
);

-- Convenient KPI view (OEE-style quality + availability signals)
create or replace view factory_daily_kpis as
select
  m.tenant_id,
  l.plant,
  l.line_name,
  m.shift_date,
  sum(m.units_produced) as units_produced,
  sum(m.units_defective) as units_defective,
  round(100.0 * sum(m.units_defective) / nullif(sum(m.units_produced),0), 2) as defect_rate_pct,
  sum(m.downtime_minutes) as downtime_minutes,
  round(100.0 * sum(m.units_produced) / nullif(l.target_units_per_shift * count(*),0), 2) as target_attainment_pct
from production_metrics m
join factory_lines l on l.id = m.line_id
group by m.tenant_id, l.plant, l.line_name, m.shift_date, l.target_units_per_shift;

-- =====================================================================
-- Row Level Security
-- The FastAPI service uses the service_role key (bypasses RLS) and enforces
-- tenancy itself via API keys. RLS protects direct dashboard/client access.
-- =====================================================================
do $$
declare t text;
begin
  foreach t in array array[
    'agents','workflow_runs','agent_tasks','agent_memory','quality_scores',
    'documents','factory_lines','production_metrics','reports','api_keys'
  ] loop
    execute format('alter table %I enable row level security', t);
    execute format('drop policy if exists tenant_isolation on %I', t);
    execute format(
      'create policy tenant_isolation on %I for all
         using (tenant_id in (select public.my_tenants()))
         with check (tenant_id in (select public.my_tenants()))', t);
  end loop;
end $$;

alter table tenants enable row level security;
drop policy if exists tenant_read on tenants;
create policy tenant_read on tenants for select
  using (id in (select public.my_tenants()));

alter table tenant_members enable row level security;
drop policy if exists member_read on tenant_members;
create policy member_read on tenant_members for select
  using (user_id = auth.uid());

-- The view runs with the caller's rights so RLS on base tables applies.
alter view factory_daily_kpis set (security_invoker = true);

-- =====================================================================
-- Seed: one demo tenant, 2 lines, 7 days of sample data, 3 agents
-- =====================================================================
insert into tenants (id, name, plan)
values ('11111111-1111-1111-1111-111111111111', 'Demo Plant Co', 'pro')
on conflict do nothing;

insert into agents (tenant_id, name, kind) values
  ('11111111-1111-1111-1111-111111111111','Researcher','research'),
  ('11111111-1111-1111-1111-111111111111','Summarizer','summarizer'),
  ('11111111-1111-1111-1111-111111111111','Analyst','analytics')
on conflict do nothing;

insert into factory_lines (tenant_id, plant, line_name, product, target_units_per_shift) values
  ('11111111-1111-1111-1111-111111111111','Jaipur Plant','Line-1','Brake Pads',1200),
  ('11111111-1111-1111-1111-111111111111','Jaipur Plant','Line-2','Gaskets',900)
on conflict do nothing;

insert into production_metrics (tenant_id, line_id, shift_date, shift, units_produced, units_defective, downtime_minutes, downtime_reason)
select
  '11111111-1111-1111-1111-111111111111', l.id, d::date, s,
  (l.target_units_per_shift * (0.8 + random()*0.25))::int,
  (l.target_units_per_shift * random()*0.04)::int,
  (random()*45)::int,
  case when random() > 0.6 then (array['Machine jam','Material shortage','Tool change','Power fluctuation'])[1 + (random()*3)::int] end
from factory_lines l
cross join generate_series(current_date - 6, current_date, interval '1 day') d
cross join unnest(array['A','B','C']) s
on conflict do nothing;

-- Create an API key manually (replace the plaintext with your own secret):
--   insert into api_keys (tenant_id, name, key_hash)
--   values ('11111111-1111-1111-1111-111111111111','n8n',
--           encode(digest('YOUR_SECRET_KEY','sha256'),'hex'));
