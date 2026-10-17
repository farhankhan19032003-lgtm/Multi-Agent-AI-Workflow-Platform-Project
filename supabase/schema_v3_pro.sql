-- =====================================================================
-- Agent Factory v3 (Pro): company data library, settings, invites, usage
-- Run AFTER schema.sql and schema_v2_chat.sql
-- =====================================================================

alter table tenant_members add column if not exists email text;
alter table tenant_members add column if not exists joined_at timestamptz not null default now();

-- Files and tables a company uploaded (the data itself lives in a per-tenant DuckDB file on the server)
create table if not exists data_sources (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  name text not null,
  kind text not null default 'table' check (kind in ('table','document')),
  filename text,
  sheet text,
  rows bigint not null default 0,
  columns jsonb not null default '[]'::jsonb,    -- column profile used to prompt the agents
  size_bytes bigint not null default 0,
  is_sample boolean not null default false,
  uploaded_by text,
  created_at timestamptz not null default now(),
  unique (tenant_id, name)
);

-- ChatGPT-style custom instructions
create table if not exists user_settings (
  tenant_id uuid not null references tenants(id) on delete cascade,
  owner text not null,
  about text not null default '',
  style text not null default '',
  updated_at timestamptz not null default now(),
  primary key (tenant_id, owner)
);

-- Workspace invite links
create table if not exists invites (
  token text primary key,
  tenant_id uuid not null references tenants(id) on delete cascade,
  role text not null default 'member' check (role in ('admin','member')),
  created_by text,
  expires_at timestamptz not null,
  uses int not null default 0,
  created_at timestamptz not null default now()
);

-- Daily usage per user (drives the free/pro message limits)
create table if not exists usage_daily (
  tenant_id uuid not null references tenants(id) on delete cascade,
  owner text not null,
  day date not null,
  messages int not null default 0,
  tokens_in bigint not null default 0,
  tokens_out bigint not null default 0,
  primary key (tenant_id, owner, day)
);

do $$
declare t text;
begin
  foreach t in array array['data_sources','user_settings','invites','usage_daily'] loop
    execute format('alter table %I enable row level security', t);
    execute format('drop policy if exists tenant_isolation on %I', t);
    execute format(
      'create policy tenant_isolation on %I for all
         using (tenant_id in (select public.my_tenants()))
         with check (tenant_id in (select public.my_tenants()))', t);
  end loop;
end $$;

-- Upgrade a customer to Pro (until you wire up a payment provider):
--   update tenants set plan = 'pro' where id = '<tenant uuid>';
