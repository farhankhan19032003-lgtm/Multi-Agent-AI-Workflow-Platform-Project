-- =====================================================================
-- Agent Factory v2: chat history (run AFTER schema.sql)
-- =====================================================================

create table if not exists conversations (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  owner text not null,                 -- auth user id, 'dev', or 'apikey'
  title text not null default 'New chat',
  agent_id text not null default 'auto',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_conv_owner on conversations (tenant_id, owner, updated_at desc);

create table if not exists messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references conversations(id) on delete cascade,
  tenant_id uuid not null references tenants(id) on delete cascade,
  role text not null check (role in ('user','assistant')),
  content text not null,
  meta jsonb not null default '{}'::jsonb,   -- agent, tool traces, charts, token usage
  created_at timestamptz not null default now()
);
create index if not exists idx_msg_conv on messages (conversation_id, created_at);

do $$
declare t text;
begin
  foreach t in array array['conversations','messages'] loop
    execute format('alter table %I enable row level security', t);
    execute format('drop policy if exists tenant_isolation on %I', t);
    execute format(
      'create policy tenant_isolation on %I for all
         using (tenant_id in (select public.my_tenants()))
         with check (tenant_id in (select public.my_tenants()))', t);
  end loop;
end $$;
