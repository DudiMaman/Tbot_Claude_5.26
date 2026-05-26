-- Building Management — Billing: ChargeSchedule, Charge, Payment, PaymentMethod
-- See SPEC.md §11

create type charge_status     as enum ('pending', 'paid', 'partial', 'overdue', 'cancelled', 'refunded', 'unbilled_no_payer');
create type payment_status    as enum ('pending', 'captured', 'failed', 'refunded');
create type payment_method    as enum ('card', 'cash', 'check', 'wire', 'other');
create type schedule_cadence  as enum ('one_off', 'monthly', 'quarterly', 'annual');
create type schedule_status   as enum ('active', 'paused', 'ended');
create type card_brand        as enum ('visa', 'mastercard', 'amex', 'isracard', 'leumicard', 'diners', 'unknown');

-- ============================================================
-- ChargeSchedule — recurring billing definitions
-- ============================================================

create table charge_schedules (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  building_id uuid not null references buildings(id) on delete cascade,
  apartment_id uuid references apartments(id) on delete cascade,
  name text not null,
  description text,
  amount numeric(12, 2) not null,
  currency text not null default 'ILS',
  cadence schedule_cadence not null,
  day_of_month int,
  start_date date not null,
  end_date date,
  installments_allowed int not null default 1,
  bill_payer_rule bill_payer_rule not null default 'current_bill_payer',
  bill_payer_person_id uuid references people(id),
  status schedule_status not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint installments_range check (installments_allowed between 1 and 12),
  constraint dom_range check (day_of_month is null or (day_of_month between 1 and 31)),
  constraint dates_check check (end_date is null or end_date >= start_date),
  constraint specific_person_set check (
    bill_payer_rule <> 'specific_person_id' or bill_payer_person_id is not null
  )
);

create index charge_schedules_tenant_idx on charge_schedules(tenant_id);
create index charge_schedules_building_idx on charge_schedules(building_id);
create index charge_schedules_apartment_idx on charge_schedules(apartment_id) where apartment_id is not null;
create index charge_schedules_active_idx on charge_schedules(tenant_id, status) where status = 'active';

create trigger trg_charge_schedules_updated_at
  before update on charge_schedules
  for each row execute function set_updated_at();

-- ============================================================
-- Charge — single instance of a debt against a specific person
-- ============================================================

create table charges (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  building_id uuid not null references buildings(id),
  apartment_id uuid not null references apartments(id),
  billed_to_person_id uuid references people(id),
  schedule_id uuid references charge_schedules(id),
  description text,
  amount numeric(12, 2) not null,
  currency text not null default 'ILS',
  due_date date not null,
  status charge_status not null default 'pending',
  invoice_id uuid, -- forward reference; set when invoice issued
  invoice_number text,
  vat_amount numeric(12, 2),
  paid_amount numeric(12, 2) not null default 0,
  last_reminder_at timestamptz,
  dunning_stage int not null default 0,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint amounts_nonneg check (amount >= 0 and paid_amount >= 0),
  constraint dunning_range check (dunning_stage between 0 and 5)
);

create index charges_tenant_status_due_idx on charges(tenant_id, status, due_date);
create index charges_tenant_person_idx on charges(tenant_id, billed_to_person_id, status);
create index charges_apartment_idx on charges(apartment_id, due_date desc);
create index charges_schedule_idx on charges(schedule_id) where schedule_id is not null;
create index charges_unbilled_idx on charges(tenant_id) where status = 'unbilled_no_payer';

create trigger trg_charges_updated_at
  before update on charges
  for each row execute function set_updated_at();

-- ============================================================
-- PaymentMethod — Tranzila tokenized card stored per person
-- ============================================================

create table payment_methods (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  owner_person_id uuid not null references people(id) on delete cascade,
  type payment_method not null default 'card',
  tranzila_token text,
  brand card_brand not null default 'unknown',
  last4 text,
  expiry_month int,
  expiry_year int,
  is_default boolean not null default false,
  status text not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint last4_format check (last4 is null or last4 ~ '^[0-9]{4}$'),
  constraint expiry_check check (
    (expiry_month is null and expiry_year is null) or
    (expiry_month between 1 and 12 and expiry_year >= 2020)
  )
);

create index payment_methods_owner_idx on payment_methods(owner_person_id) where status = 'active';
create unique index payment_methods_default_per_owner
  on payment_methods(owner_person_id)
  where is_default = true and status = 'active';

create trigger trg_payment_methods_updated_at
  before update on payment_methods
  for each row execute function set_updated_at();

-- ============================================================
-- Payment — one payment attempt against a charge
-- Note: paid_by_person_id may differ from charges.billed_to_person_id
-- (e.g., owner steps in to pay an overdue renter charge)
-- ============================================================

create table payments (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  charge_id uuid not null references charges(id) on delete cascade,
  paid_by_person_id uuid references people(id),
  payment_method_id uuid references payment_methods(id),
  method payment_method not null,
  amount numeric(12, 2) not null,
  currency text not null default 'ILS',
  status payment_status not null default 'pending',
  tranzila_token_id text,
  tranzila_txn_id text,
  last4 text,
  brand card_brand,
  installments int not null default 1,
  captured_at timestamptz,
  failure_reason text,
  raw_provider_json jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint installments_range_pay check (installments between 1 and 12)
);

create index payments_tenant_idx on payments(tenant_id);
create index payments_charge_idx on payments(charge_id);
create index payments_payer_idx on payments(paid_by_person_id);
create index payments_status_idx on payments(tenant_id, status, captured_at desc);
create unique index payments_tranzila_txn_idx on payments(tranzila_txn_id) where tranzila_txn_id is not null;

create trigger trg_payments_updated_at
  before update on payments
  for each row execute function set_updated_at();

-- ============================================================
-- Trigger: keep charges.paid_amount and status in sync with payments
-- ============================================================

create or replace function recompute_charge_paid_amount()
returns trigger as $$
declare
  v_charge_id uuid;
  v_total_paid numeric(12, 2);
  v_charge_amount numeric(12, 2);
begin
  v_charge_id := coalesce(new.charge_id, old.charge_id);

  select coalesce(sum(amount), 0)
    into v_total_paid
    from payments
    where charge_id = v_charge_id and status = 'captured';

  select amount into v_charge_amount from charges where id = v_charge_id;

  update charges
    set paid_amount = v_total_paid,
        status = case
          when v_total_paid >= v_charge_amount then 'paid'
          when v_total_paid > 0 then 'partial'
          when due_date < current_date then 'overdue'
          else 'pending'
        end
    where id = v_charge_id
      and status not in ('cancelled', 'refunded');

  return null;
end;
$$ language plpgsql;

create trigger trg_payment_change_recompute_charge
  after insert or update of status, amount or delete on payments
  for each row execute function recompute_charge_paid_amount();
