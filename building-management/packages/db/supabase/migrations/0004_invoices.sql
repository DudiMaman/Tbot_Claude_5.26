-- Building Management — Tax-compliant Invoices & Receipts
-- See SPEC.md §37
--
-- Israeli tax law requires gap-free sequential numbering, specific document
-- types, and (above thresholds) digital ITA clearance with allocation number.

create type invoice_type            as enum ('tax_invoice', 'receipt', 'tax_invoice_receipt', 'credit_note');
create type invoice_status          as enum ('draft', 'issued', 'sent', 'cancelled', 'replaced');
create type ita_clearance_status    as enum ('not_required', 'requested', 'approved', 'rejected');

-- ============================================================
-- InvoiceSeries — one per (tenant, type) by default; enterprise can have per-building
-- ============================================================

create table invoice_series (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  building_id uuid references buildings(id) on delete cascade,
  document_type invoice_type not null,
  name text not null,
  prefix text not null default '',
  next_serial bigint not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  -- One series per (tenant, type) when building is null
  unique (tenant_id, document_type, building_id)
);

create index invoice_series_tenant_idx on invoice_series(tenant_id);

create trigger trg_invoice_series_updated_at
  before update on invoice_series
  for each row execute function set_updated_at();

-- ============================================================
-- Invoices (covers tax invoice, receipt, combined, credit note)
-- ============================================================

create table invoices (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  building_id uuid references buildings(id),
  apartment_id uuid references apartments(id),
  series_id uuid not null references invoice_series(id),
  type invoice_type not null,
  serial_number bigint, -- assigned at issuance, not draft
  status invoice_status not null default 'draft',
  issued_at timestamptz,
  issued_by_user_id uuid,
  customer_person_id uuid references people(id),

  -- Snapshots captured at issuance (immutable for legal reasons)
  customer_name_snapshot text,
  customer_address_snapshot text,
  customer_vat_id_snapshot text,

  description text,
  currency text not null default 'ILS',
  subtotal numeric(12, 2) not null default 0,
  vat_rate_pct numeric(5, 2) not null default 17,
  vat_amount numeric(12, 2) not null default 0,
  total numeric(12, 2) not null default 0,

  related_charge_ids uuid[] not null default '{}',
  related_payment_ids uuid[] not null default '{}',
  credit_note_for_invoice_id uuid references invoices(id),

  pdf_file_id uuid,

  ita_allocation_number text,
  ita_clearance_status ita_clearance_status not null default 'not_required',
  ita_clearance_payload jsonb,

  delivered_channels jsonb not null default '{}'::jsonb,
  content_hash text,
  metadata jsonb not null default '{}'::jsonb,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint serial_assigned_when_issued check (
    (status = 'draft' and serial_number is null) or
    (status <> 'draft' and serial_number is not null)
  ),
  constraint totals_consistent check (
    abs(total - (subtotal + vat_amount)) < 0.01
  ),
  constraint credit_note_link check (
    (type = 'credit_note' and credit_note_for_invoice_id is not null) or
    (type <> 'credit_note' and credit_note_for_invoice_id is null)
  )
);

create unique index invoices_series_serial_idx
  on invoices(series_id, serial_number)
  where serial_number is not null;

create index invoices_tenant_idx on invoices(tenant_id);
create index invoices_customer_idx on invoices(customer_person_id);
create index invoices_apartment_idx on invoices(apartment_id);
create index invoices_status_idx on invoices(tenant_id, status, issued_at desc);
create index invoices_type_idx on invoices(tenant_id, type);

create trigger trg_invoices_updated_at
  before update on invoices
  for each row execute function set_updated_at();

-- Now link charges.invoice_id forward
alter table charges
  add constraint charges_invoice_fk
  foreign key (invoice_id) references invoices(id) on delete set null;

-- ============================================================
-- Invoice line items
-- ============================================================

create table invoice_line_items (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  invoice_id uuid not null references invoices(id) on delete cascade,
  position int not null,
  description text not null,
  quantity numeric(12, 4) not null default 1,
  unit_price numeric(12, 2) not null,
  subtotal numeric(12, 2) not null,
  vat_rate_pct numeric(5, 2) not null default 17,
  vat_amount numeric(12, 2) not null,
  total numeric(12, 2) not null,
  related_charge_id uuid references charges(id),
  metadata jsonb not null default '{}'::jsonb
);

create index invoice_line_items_invoice_idx on invoice_line_items(invoice_id);

-- ============================================================
-- Function: allocate next sequential number atomically
-- ============================================================

create or replace function allocate_invoice_serial(p_series_id uuid)
returns bigint as $$
declare
  v_next bigint;
begin
  update invoice_series
    set next_serial = next_serial + 1,
        updated_at = now()
    where id = p_series_id
    returning next_serial - 1 into v_next;

  if v_next is null then
    raise exception 'Invoice series % not found', p_series_id;
  end if;

  return v_next;
end;
$$ language plpgsql;
