-- Building Management — Master schema, Part 1: Tenants, Buildings, Apartments, People
-- See SPEC.md §3, §4

create extension if not exists pgcrypto;
create extension if not exists "uuid-ossp";
create extension if not exists postgis;
create extension if not exists pg_trgm;

-- ============================================================
-- Enums
-- ============================================================

create type tenant_plan        as enum ('trial', 'starter', 'pro', 'enterprise');
create type user_role          as enum ('mgmt_admin', 'mgmt_member', 'maintenance', 'resident');
create type apartment_role     as enum ('owner', 'renter', 'family_member', 'authorized_contact');
create type apartment_occupancy as enum ('vacant', 'owner_occupied', 'rented', 'mixed');
create type assignment_status  as enum ('active', 'pending', 'ended', 'superseded');
create type bill_payer_rule    as enum ('current_bill_payer', 'specific_person_id', 'owner', 'primary_occupant');
create type vaad_responsibility as enum ('renter_pays', 'owner_pays', 'split');
create type rental_status      as enum ('draft', 'active', 'ended', 'terminated');
create type claim_status       as enum ('pending', 'approved', 'rejected');
create type tenant_status      as enum ('active', 'suspended', 'cancelled');

-- ============================================================
-- Tenants (one customer of the SaaS = one management company)
-- ============================================================

create table tenants (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  legal_name text,
  vat_id text,
  billing_email text not null,
  plan tenant_plan not null default 'trial',
  trial_ends_at timestamptz,
  locale text not null default 'he-IL',
  timezone text not null default 'Asia/Jerusalem',
  branding jsonb not null default '{}'::jsonb,
  features jsonb not null default '{}'::jsonb,
  status tenant_status not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index tenants_status_idx on tenants(status);

-- ============================================================
-- Buildings
-- ============================================================

create table buildings (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  name text not null,
  address_line text not null,
  city text not null,
  postal_code text,
  geo geography(point, 4326),
  num_floors int,
  num_apartments int,
  year_built int,
  bank_account_iban text,
  claim_secret text not null default encode(gen_random_bytes(16), 'hex'),
  notes text,
  settings jsonb not null default '{}'::jsonb,
  notification_policy jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);

create index buildings_tenant_idx on buildings(tenant_id);
create index buildings_geo_idx on buildings using gist (geo);
create index buildings_tenant_created_idx on buildings(tenant_id, created_at desc);

-- ============================================================
-- Apartments
-- ============================================================

create table apartments (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  building_id uuid not null references buildings(id) on delete cascade,
  unit_number text not null,
  floor int,
  size_sqm numeric(8, 2),
  num_rooms numeric(3, 1),
  occupancy_status apartment_occupancy not null default 'vacant',
  monthly_dues_amount numeric(12, 2),
  notification_policy jsonb not null default '{}'::jsonb,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz,
  unique (building_id, unit_number)
);

create index apartments_tenant_building_idx on apartments(tenant_id, building_id);
create index apartments_tenant_created_idx on apartments(tenant_id, created_at desc);

-- ============================================================
-- People (master person records — PII lives here exactly once per tenant)
-- A Person may be linked to zero, one, or many apartments via apartment_assignments
-- ============================================================

create table people (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  full_name text not null,
  id_number_encrypted bytea,
  phone_e164 text,
  email text,
  language text not null default 'he',
  push_token text,
  whatsapp_opt_in boolean not null default false,
  claim_status claim_status not null default 'pending',
  claim_method text,
  supabase_user_id uuid,
  notification_prefs jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);

create index people_tenant_phone_idx on people(tenant_id, phone_e164);
create index people_tenant_email_idx on people(tenant_id, email);
create unique index people_supabase_user_idx on people(supabase_user_id) where supabase_user_id is not null;
create index people_tenant_created_idx on people(tenant_id, created_at desc);

-- ============================================================
-- Management users (employees of management company)
-- ============================================================

create table management_users (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  full_name text not null,
  email text not null,
  phone_e164 text,
  role user_role not null,
  permissions jsonb not null default '{}'::jsonb,
  supabase_user_id uuid,
  last_login_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz,
  constraint management_users_role_check check (role in ('mgmt_admin', 'mgmt_member'))
);

create unique index management_users_tenant_email_idx on management_users(tenant_id, email);
create unique index management_users_supabase_user_idx on management_users(supabase_user_id) where supabase_user_id is not null;

-- ============================================================
-- Maintenance workers
-- ============================================================

create table maintenance_workers (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  full_name text not null,
  phone_e164 text not null,
  email text,
  skills jsonb not null default '[]'::jsonb,
  employment_type text not null default 'employee',
  hourly_rate numeric(10, 2),
  supabase_user_id uuid,
  status text not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);

create index maintenance_workers_tenant_idx on maintenance_workers(tenant_id);
create unique index maintenance_workers_supabase_user_idx on maintenance_workers(supabase_user_id) where supabase_user_id is not null;

create table worker_building_assignments (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  worker_id uuid not null references maintenance_workers(id) on delete cascade,
  building_id uuid not null references buildings(id) on delete cascade,
  created_at timestamptz not null default now(),
  unique (worker_id, building_id)
);

create index worker_building_assignments_tenant_idx on worker_building_assignments(tenant_id);

-- ============================================================
-- Auto-update updated_at trigger
-- ============================================================

create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger trg_tenants_updated_at before update on tenants for each row execute function set_updated_at();
create trigger trg_buildings_updated_at before update on buildings for each row execute function set_updated_at();
create trigger trg_apartments_updated_at before update on apartments for each row execute function set_updated_at();
create trigger trg_people_updated_at before update on people for each row execute function set_updated_at();
create trigger trg_management_users_updated_at before update on management_users for each row execute function set_updated_at();
create trigger trg_maintenance_workers_updated_at before update on maintenance_workers for each row execute function set_updated_at();
