-- Building Management — Apartment Assignments + Rental Contracts
-- See SPEC.md §3.6 — Ownership vs Occupancy vs Billing (CRITICAL domain)
--
-- An apartment may have multiple people linked to it with different roles
-- (owner, renter, family_member). Exactly one of them may be the current
-- "bill payer" (the one responsible for paying the va'ad fees).
--
-- A rental contract formalizes the owner↔renter relationship and dictates
-- who is responsible for the va'ad fees.

-- ============================================================
-- Apartment Assignments
-- ============================================================

create table apartment_assignments (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  apartment_id uuid not null references apartments(id) on delete cascade,
  person_id uuid not null references people(id) on delete cascade,
  role apartment_role not null,
  is_primary boolean not null default false,
  is_occupant boolean not null default false,
  is_bill_payer boolean not null default false,
  share_pct numeric(5, 2),
  valid_from date not null default current_date,
  valid_to date,
  rental_contract_id uuid,
  notes text,
  status assignment_status not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint share_pct_range check (share_pct is null or (share_pct >= 0 and share_pct <= 100)),
  constraint valid_dates check (valid_to is null or valid_to >= valid_from),
  -- A renter must always be the occupant
  constraint renter_occupies check (role <> 'renter' or is_occupant = true)
);

-- Exactly one current (active + open-ended) bill payer per apartment.
create unique index one_current_bill_payer_per_apt
  on apartment_assignments(apartment_id)
  where is_bill_payer = true
    and valid_to is null
    and status = 'active';

-- Exactly one primary per (apartment, role) at a time.
create unique index one_primary_per_role_per_apt
  on apartment_assignments(apartment_id, role)
  where is_primary = true
    and valid_to is null
    and status = 'active';

create index apartment_assignments_current_idx
  on apartment_assignments(tenant_id, apartment_id)
  where status = 'active' and valid_to is null;

create index apartment_assignments_person_idx
  on apartment_assignments(tenant_id, person_id);

create index apartment_assignments_tenant_idx on apartment_assignments(tenant_id);
create index apartment_assignments_apartment_idx on apartment_assignments(apartment_id);

create trigger trg_apartment_assignments_updated_at
  before update on apartment_assignments
  for each row execute function set_updated_at();

-- ============================================================
-- Rental Contracts
-- ============================================================

create table rental_contracts (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  apartment_id uuid not null references apartments(id) on delete cascade,
  owner_person_id uuid not null references people(id),
  renter_person_id uuid not null references people(id),
  start_date date not null,
  end_date date,
  monthly_rent numeric(12, 2),
  vaad_responsibility vaad_responsibility not null default 'renter_pays',
  split_renter_pct numeric(5, 2),
  contract_file_id uuid,
  status rental_status not null default 'draft',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint rental_dates_check check (end_date is null or end_date >= start_date),
  constraint split_pct_required check (
    vaad_responsibility <> 'split' or
    (split_renter_pct is not null and split_renter_pct > 0 and split_renter_pct < 100)
  ),
  constraint different_parties check (owner_person_id <> renter_person_id)
);

create index rental_contracts_tenant_idx on rental_contracts(tenant_id);
create index rental_contracts_apartment_idx on rental_contracts(apartment_id);
create index rental_contracts_owner_idx on rental_contracts(owner_person_id);
create index rental_contracts_renter_idx on rental_contracts(renter_person_id);
create index rental_contracts_status_idx on rental_contracts(tenant_id, status);

-- Only one active rental contract per apartment at a time
create unique index one_active_rental_per_apartment
  on rental_contracts(apartment_id)
  where status = 'active';

create trigger trg_rental_contracts_updated_at
  before update on rental_contracts
  for each row execute function set_updated_at();

-- Link assignments.rental_contract_id once contracts exist
alter table apartment_assignments
  add constraint apartment_assignments_rental_contract_fk
  foreign key (rental_contract_id) references rental_contracts(id) on delete set null;

-- ============================================================
-- Trigger: when a rental contract is activated, sync assignments
-- ============================================================

create or replace function sync_assignments_from_rental_contract()
returns trigger as $$
declare
  v_renter_is_payer boolean;
begin
  if new.status <> 'active' then
    return new;
  end if;

  v_renter_is_payer := new.vaad_responsibility in ('renter_pays', 'split');

  -- End any prior bill_payer assignment on this apartment
  update apartment_assignments
    set is_bill_payer = false
    where apartment_id = new.apartment_id
      and is_bill_payer = true
      and status = 'active'
      and valid_to is null;

  -- Upsert owner assignment
  insert into apartment_assignments (
    tenant_id, apartment_id, person_id, role, is_primary,
    is_occupant, is_bill_payer, valid_from, rental_contract_id, status
  )
  values (
    new.tenant_id, new.apartment_id, new.owner_person_id, 'owner', true,
    false, not v_renter_is_payer, new.start_date, new.id, 'active'
  )
  on conflict do nothing;

  -- Upsert renter assignment
  insert into apartment_assignments (
    tenant_id, apartment_id, person_id, role, is_primary,
    is_occupant, is_bill_payer, valid_from, rental_contract_id, status
  )
  values (
    new.tenant_id, new.apartment_id, new.renter_person_id, 'renter', true,
    true, v_renter_is_payer, new.start_date, new.id, 'active'
  )
  on conflict do nothing;

  -- Update apartment occupancy status
  update apartments set occupancy_status = 'rented' where id = new.apartment_id;

  return new;
end;
$$ language plpgsql;

create trigger trg_sync_rental_contract_assignments
  after insert or update of status on rental_contracts
  for each row execute function sync_assignments_from_rental_contract();
