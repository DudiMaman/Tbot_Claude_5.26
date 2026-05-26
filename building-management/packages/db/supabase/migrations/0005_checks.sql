-- Building Management — Check Management (incl. bounced checks)
-- See SPEC.md §38
--
-- Israeli HOAs receive many physical checks (post-dated very common).
-- This module digitizes the entire lifecycle and handles bounced checks.

create type check_status as enum (
  'received', 'scheduled', 'deposited', 'cleared', 'bounced', 'replaced', 'voided'
);

create type batch_status as enum (
  'draft', 'deposited', 'partially_cleared', 'fully_cleared'
);

create type bounce_reason as enum (
  'insufficient_funds', 'account_closed', 'stop_payment',
  'signature_mismatch', 'wrong_date', 'amount_mismatch', 'other'
);

create type bounce_recovery_status as enum (
  'open', 'replacement_received', 'paid_other', 'legal_handover', 'written_off'
);

-- ============================================================
-- CheckBatch — group of checks deposited together at the bank
-- ============================================================

create table check_batches (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  building_id uuid not null references buildings(id),
  bank_account_iban text not null,
  deposit_date date not null,
  total_amount numeric(12, 2) not null default 0,
  status batch_status not null default 'draft',
  bank_deposit_slip_file_id uuid,
  bank_reference text,
  notes text,
  created_by_user_id uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index check_batches_tenant_idx on check_batches(tenant_id);
create index check_batches_building_idx on check_batches(building_id);
create index check_batches_date_idx on check_batches(tenant_id, deposit_date desc);

create trigger trg_check_batches_updated_at
  before update on check_batches
  for each row execute function set_updated_at();

-- ============================================================
-- Check — a physical check received from a resident
-- ============================================================

create table checks (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  building_id uuid not null references buildings(id),
  apartment_id uuid references apartments(id),
  payer_person_id uuid references people(id),

  -- Israeli check identification (3 numeric fields printed on every check)
  bank_code text not null,
  branch_code text not null,
  account_number text not null,
  check_number text not null,

  amount numeric(12, 2) not null,
  currency text not null default 'ILS',
  issue_date date not null,
  presented_date date not null default current_date,
  due_date date not null, -- = issue_date for current; later for post-dated
  scan_file_id uuid,
  status check_status not null default 'received',
  deposit_batch_id uuid references check_batches(id),
  related_charge_ids uuid[] not null default '{}',
  received_by_user_id uuid, -- mgmt user or maintenance worker
  notes text,
  metadata jsonb not null default '{}'::jsonb,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint amount_positive check (amount > 0),
  constraint due_date_check check (due_date >= issue_date)
);

create index checks_tenant_idx on checks(tenant_id);
create index checks_building_idx on checks(building_id);
create index checks_apartment_idx on checks(apartment_id);
create index checks_payer_idx on checks(payer_person_id);
create index checks_status_idx on checks(tenant_id, status, due_date);
create index checks_batch_idx on checks(deposit_batch_id) where deposit_batch_id is not null;
create index checks_due_date_idx on checks(tenant_id, due_date) where status in ('received', 'scheduled');

create trigger trg_checks_updated_at
  before update on checks
  for each row execute function set_updated_at();

-- ============================================================
-- BouncedCheck — workflow for handling a bounced check
-- ============================================================

create table bounced_checks (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  original_check_id uuid not null references checks(id) on delete cascade,
  bounce_reason bounce_reason not null,
  bounce_reason_text text,
  bounced_on date not null default current_date,
  bank_fee_amount numeric(12, 2) not null default 0,
  recharge_fee_amount numeric(12, 2) not null default 0,
  recovery_status bounce_recovery_status not null default 'open',
  replacement_check_id uuid references checks(id),
  replacement_payment_id uuid, -- forward ref
  legal_handover_at timestamptz,
  resolution_notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index bounced_checks_original_idx on bounced_checks(original_check_id);
create index bounced_checks_tenant_status_idx on bounced_checks(tenant_id, recovery_status);

create trigger trg_bounced_checks_updated_at
  before update on bounced_checks
  for each row execute function set_updated_at();

-- ============================================================
-- Function: when a check is marked bounced, revert charges + create fee
-- (Wired up by application layer rather than trigger to keep it explicit.
--  The trigger only sets timestamps and integrity.)
-- ============================================================

create or replace function on_check_bounced()
returns trigger as $$
begin
  if new.status = 'bounced' and old.status <> 'bounced' then
    -- Revert related charges to overdue/pending
    update charges
      set status = case when due_date < current_date then 'overdue' else 'pending' end,
          paid_amount = greatest(paid_amount - new.amount, 0)
      where id = any(new.related_charge_ids)
        and status in ('paid', 'partial');
  end if;
  return new;
end;
$$ language plpgsql;

create trigger trg_check_status_change_revert_charges
  after update of status on checks
  for each row execute function on_check_bounced();
