-- Building Management — Vendors + Addons + Access Control
-- See SPEC.md §12, §19, §20

create type vendor_status as enum ('active', 'inactive', 'blocked');
create type vendor_invoice_status as enum ('received', 'approved', 'scheduled', 'paid', 'rejected');
create type vendor_payout_method as enum ('tranzila', 'masav', 'wire');
create type vendor_payout_status as enum ('scheduled', 'sent', 'confirmed', 'failed');
create type addon_status as enum ('active', 'inactive', 'archived');
create type addon_order_status as enum ('pending', 'in_progress', 'delivered', 'cancelled');
create type gate_kind as enum ('parking', 'pedestrian', 'service');
create type gate_provider as enum ('http_webhook', 'mqtt', 'sesame', 'custom');
create type access_action as enum ('open', 'deny');

-- ============================================================
-- Vendors
-- ============================================================

create table vendors (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  name text not null,
  contact_name text,
  phone text,
  email text,
  vat_id text,
  iban text,
  services jsonb not null default '[]'::jsonb,
  rating numeric(3, 2),
  notes text,
  status vendor_status not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);

create index vendors_tenant_idx on vendors(tenant_id);
create index vendors_status_idx on vendors(tenant_id, status);

create trigger trg_vendors_updated_at before update on vendors
  for each row execute function set_updated_at();

create table vendor_invoices (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  vendor_id uuid not null references vendors(id) on delete cascade,
  building_id uuid references buildings(id),
  invoice_number text,
  issue_date date,
  due_date date,
  amount numeric(12, 2) not null,
  vat_amount numeric(12, 2) not null default 0,
  currency text not null default 'ILS',
  file_id uuid,
  status vendor_invoice_status not null default 'received',
  approver_id uuid,
  approved_at timestamptz,
  notes text,
  ai_extracted jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index vendor_invoices_tenant_idx on vendor_invoices(tenant_id);
create index vendor_invoices_vendor_idx on vendor_invoices(vendor_id);
create index vendor_invoices_status_idx on vendor_invoices(tenant_id, status);

create trigger trg_vendor_invoices_updated_at before update on vendor_invoices
  for each row execute function set_updated_at();

create table vendor_payouts (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  vendor_id uuid not null references vendors(id),
  invoice_ids uuid[] not null default '{}',
  amount numeric(12, 2) not null,
  method vendor_payout_method not null,
  masav_file_id uuid,
  scheduled_for timestamptz,
  executed_at timestamptz,
  status vendor_payout_status not null default 'scheduled',
  reference_number text,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index vendor_payouts_tenant_idx on vendor_payouts(tenant_id);
create index vendor_payouts_status_idx on vendor_payouts(tenant_id, status);

create trigger trg_vendor_payouts_updated_at before update on vendor_payouts
  for each row execute function set_updated_at();

-- ============================================================
-- Addon Products
-- ============================================================

create table addon_products (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  sku text not null,
  name text not null,
  description text,
  price numeric(12, 2) not null,
  currency text not null default 'ILS',
  vat_inclusive boolean not null default true,
  availability_buildings uuid[] not null default '{}',
  inventory int,
  commission_pct numeric(5, 2) not null default 0,
  image_file_id uuid,
  status addon_status not null default 'active',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz,
  unique (tenant_id, sku)
);

create index addon_products_tenant_status_idx on addon_products(tenant_id, status);

create trigger trg_addon_products_updated_at before update on addon_products
  for each row execute function set_updated_at();

create table addon_orders (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  product_id uuid not null references addon_products(id),
  ordered_by_person_id uuid not null references people(id),
  building_id uuid references buildings(id),
  apartment_id uuid references apartments(id),
  qty int not null default 1,
  total numeric(12, 2) not null,
  payment_id uuid references payments(id),
  fulfillment_status addon_order_status not null default 'pending',
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint qty_positive check (qty > 0)
);

create index addon_orders_tenant_idx on addon_orders(tenant_id);
create index addon_orders_person_idx on addon_orders(ordered_by_person_id);

create trigger trg_addon_orders_updated_at before update on addon_orders
  for each row execute function set_updated_at();

-- ============================================================
-- Access Control (parking gates etc.)
-- ============================================================

create table access_gates (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  building_id uuid not null references buildings(id) on delete cascade,
  name text not null,
  kind gate_kind not null,
  provider gate_provider not null,
  config jsonb not null default '{}'::jsonb,
  status text not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index access_gates_building_idx on access_gates(building_id);

create trigger trg_access_gates_updated_at before update on access_gates
  for each row execute function set_updated_at();

create table guest_codes (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  building_id uuid not null references buildings(id) on delete cascade,
  gate_id uuid references access_gates(id) on delete cascade,
  code text not null,
  created_by_person_id uuid not null references people(id),
  valid_from timestamptz not null default now(),
  valid_to timestamptz not null,
  max_uses int not null default 1,
  uses int not null default 0,
  status text not null default 'active',
  created_at timestamptz not null default now(),
  constraint valid_window check (valid_to > valid_from)
);

create unique index guest_codes_code_idx on guest_codes(code) where status = 'active';
create index guest_codes_building_idx on guest_codes(building_id);

create table access_events (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  gate_id uuid not null references access_gates(id),
  person_id uuid references people(id),
  guest_code_id uuid references guest_codes(id),
  action access_action not null,
  source text not null default 'app',
  latency_ms int,
  metadata jsonb,
  created_at timestamptz not null default now()
);

create index access_events_gate_idx on access_events(gate_id, created_at desc);
create index access_events_tenant_idx on access_events(tenant_id, created_at desc);
