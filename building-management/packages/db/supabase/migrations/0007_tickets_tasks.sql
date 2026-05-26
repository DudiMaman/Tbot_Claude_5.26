-- Building Management — Service Tickets + Tasks
-- See SPEC.md §17 + §18

create type ticket_intake_channel as enum ('app', 'whatsapp', 'bot', 'phone', 'walkin', 'email');
create type ticket_status as enum (
  'new', 'triaged', 'assigned', 'in_progress', 'pending_parts', 'resolved', 'closed'
);
create type ticket_category as enum (
  'plumbing', 'electrical', 'elevator', 'cleaning', 'security',
  'hvac', 'common_area', 'access', 'billing', 'other'
);
create type ticket_priority as enum ('low', 'med', 'high', 'urgent');

create type task_status as enum ('todo', 'in_progress', 'blocked', 'done', 'cancelled');
create type task_source as enum ('planned', 'ticket', 'adhoc');

-- ============================================================
-- Service Tickets
-- ============================================================

create table service_tickets (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  building_id uuid not null references buildings(id),
  apartment_id uuid references apartments(id),
  opened_by_person_id uuid references people(id),
  intake_channel ticket_intake_channel not null default 'app',
  title text not null,
  description text,
  category ticket_category not null default 'other',
  priority ticket_priority not null default 'med',
  photos jsonb not null default '[]'::jsonb,
  videos jsonb not null default '[]'::jsonb,
  status ticket_status not null default 'new',
  assigned_task_id uuid,
  sla_due_at timestamptz,
  satisfaction_rating int,
  resolution_note text,
  opened_at timestamptz not null default now(),
  resolved_at timestamptz,
  closed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint satisfaction_range check (
    satisfaction_rating is null or (satisfaction_rating between 1 and 5)
  )
);

create index service_tickets_tenant_status_idx on service_tickets(tenant_id, status, sla_due_at);
create index service_tickets_building_idx on service_tickets(building_id, status);
create index service_tickets_apartment_idx on service_tickets(apartment_id);
create index service_tickets_opener_idx on service_tickets(opened_by_person_id);

create trigger trg_service_tickets_updated_at
  before update on service_tickets
  for each row execute function set_updated_at();

-- ============================================================
-- Tasks
-- ============================================================

create table tasks (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  building_id uuid not null references buildings(id),
  apartment_id uuid references apartments(id),
  source task_source not null default 'adhoc',
  source_ticket_id uuid references service_tickets(id),
  title text not null,
  description_md text,
  category ticket_category not null default 'other',
  priority ticket_priority not null default 'med',
  assigned_worker_id uuid references maintenance_workers(id),
  scheduled_at timestamptz,
  sla_due_at timestamptz,
  started_at timestamptz,
  completed_at timestamptz,
  status task_status not null default 'todo',
  checklist jsonb not null default '[]'::jsonb,
  time_spent_minutes int not null default 0,
  cost_amount numeric(12, 2),
  customer_visible boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index tasks_tenant_idx on tasks(tenant_id);
create index tasks_worker_scheduled_idx on tasks(assigned_worker_id, scheduled_at) where assigned_worker_id is not null;
create index tasks_status_idx on tasks(tenant_id, status, scheduled_at);
create index tasks_building_idx on tasks(building_id, status);
create index tasks_ticket_idx on tasks(source_ticket_id) where source_ticket_id is not null;

create trigger trg_tasks_updated_at
  before update on tasks
  for each row execute function set_updated_at();

-- Forward link service_tickets.assigned_task_id
alter table service_tickets
  add constraint service_tickets_assigned_task_fk
  foreign key (assigned_task_id) references tasks(id) on delete set null;

-- ============================================================
-- Ticket comments / activity log
-- ============================================================

create table ticket_comments (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  ticket_id uuid not null references service_tickets(id) on delete cascade,
  author_user_id uuid,
  author_person_id uuid,
  body text not null,
  visibility text not null default 'resident', -- resident | internal
  attachments jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  constraint visibility_check check (visibility in ('resident', 'internal'))
);

create index ticket_comments_ticket_idx on ticket_comments(ticket_id, created_at);
