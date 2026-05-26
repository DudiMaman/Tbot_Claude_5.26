-- Building Management — Document Vault Per Building
-- See SPEC.md §39
--
-- Every building accumulates documents: building permits, insurance policies,
-- vendor contracts, AGM minutes, blueprints, regulatory certificates, fire
-- safety inspections, elevator maintenance certificates.
-- All stored, version-controlled, ACL'd.

create type document_category as enum (
  'insurance', 'contract', 'minutes', 'permit', 'blueprint',
  'certificate', 'financial_report', 'rental_contract',
  'vendor_invoice', 'meeting_protocol', 'bylaws', 'other'
);

create type document_visibility as enum (
  'mgmt_only', 'owners', 'bill_payers', 'all_occupants', 'building_public'
);

create type document_status as enum ('active', 'archived', 'superseded');

create type document_acl_permission as enum ('view', 'download', 'edit');

-- ============================================================
-- Document — logical doc; references current version
-- ============================================================

create table documents (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  building_id uuid not null references buildings(id) on delete cascade,
  apartment_id uuid references apartments(id) on delete cascade,
  title text not null,
  category document_category not null,
  description text,
  expires_at date,
  reminder_lead_days int not null default 30,
  tags text[] not null default '{}',
  current_version_id uuid,
  visibility document_visibility not null default 'mgmt_only',
  status document_status not null default 'active',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz,
  constraint reminder_lead_nonneg check (reminder_lead_days >= 0)
);

create index documents_tenant_idx on documents(tenant_id);
create index documents_building_idx on documents(building_id);
create index documents_apartment_idx on documents(apartment_id) where apartment_id is not null;
create index documents_category_idx on documents(tenant_id, category);
create index documents_expires_idx on documents(tenant_id, expires_at)
  where expires_at is not null and status = 'active';

create trigger trg_documents_updated_at
  before update on documents
  for each row execute function set_updated_at();

-- ============================================================
-- DocumentVersion — versioned blob references
-- ============================================================

create table document_versions (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  document_id uuid not null references documents(id) on delete cascade,
  version_number int not null,
  file_id uuid not null,
  uploaded_by_user_id uuid,
  upload_notes text,
  size_bytes bigint not null,
  mime text,
  sha256 text,
  ocr_text text,
  ai_summary text,
  ai_metadata jsonb,
  created_at timestamptz not null default now(),
  unique (document_id, version_number)
);

create index document_versions_document_idx on document_versions(document_id, version_number desc);

-- Forward link documents.current_version_id
alter table documents
  add constraint documents_current_version_fk
  foreign key (current_version_id) references document_versions(id) on delete set null;

-- Search index on ocr_text + ai_summary
create index document_versions_text_search_idx
  on document_versions
  using gin (to_tsvector('simple', coalesce(ocr_text, '') || ' ' || coalesce(ai_summary, '')));

-- ============================================================
-- DocumentACL — per-person or per-role overrides
-- ============================================================

create table document_acls (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  document_id uuid not null references documents(id) on delete cascade,
  person_id uuid references people(id) on delete cascade,
  role text,
  permission document_acl_permission not null default 'view',
  created_at timestamptz not null default now(),
  constraint acl_target_check check (
    (person_id is not null and role is null) or
    (person_id is null and role is not null)
  )
);

create index document_acls_document_idx on document_acls(document_id);
create index document_acls_person_idx on document_acls(person_id) where person_id is not null;

-- ============================================================
-- Function: when a new version is uploaded, point current_version_id at it
-- ============================================================

create or replace function set_document_current_version()
returns trigger as $$
begin
  update documents
    set current_version_id = new.id,
        updated_at = now()
    where id = new.document_id;
  return new;
end;
$$ language plpgsql;

create trigger trg_document_versions_set_current
  after insert on document_versions
  for each row execute function set_document_current_version();
