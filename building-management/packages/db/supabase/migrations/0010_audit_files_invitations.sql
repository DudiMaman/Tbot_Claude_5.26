-- Building Management — Audit log, Files, Invitations, KB chunks
-- See SPEC.md §5.5, §14.4, §24

-- ============================================================
-- Audit Log (append-only, hash-chained)
-- ============================================================

create table audit_log (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid references tenants(id) on delete cascade,
  actor_user_id uuid,
  actor_type text not null default 'system',
  action text not null,
  entity_type text not null,
  entity_id uuid,
  before_json jsonb,
  after_json jsonb,
  ip text,
  user_agent text,
  prev_hash text,
  this_hash text,
  created_at timestamptz not null default now()
);

create index audit_log_tenant_idx on audit_log(tenant_id, created_at desc);
create index audit_log_entity_idx on audit_log(entity_type, entity_id, created_at desc);

-- ============================================================
-- Files (metadata for Supabase Storage objects)
-- ============================================================

create table files (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  owner_user_id uuid,
  owner_person_id uuid references people(id),
  bucket text not null,
  path text not null,
  mime text,
  size_bytes bigint,
  sha256 text,
  pii_tag text not null default 'none',
  virus_scan_status text not null default 'pending',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  deleted_at timestamptz,
  constraint pii_tag_check check (pii_tag in ('none', 'pii', 'financial', 'sensitive'))
);

create index files_tenant_idx on files(tenant_id);
create unique index files_bucket_path_idx on files(bucket, path);

-- ============================================================
-- Invitations (mgmt + worker onboarding)
-- ============================================================

create table invitations (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  token text not null,
  role user_role not null,
  email text,
  phone_e164 text,
  permissions jsonb,
  metadata jsonb not null default '{}'::jsonb,
  consumed_at timestamptz,
  consumed_by_user_id uuid,
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  constraint contact_required check (email is not null or phone_e164 is not null)
);

create unique index invitations_token_idx on invitations(token);
create index invitations_tenant_idx on invitations(tenant_id) where consumed_at is null;

-- ============================================================
-- KB chunks (for AI bot RAG) — uses pgvector if available
-- ============================================================

create extension if not exists vector;

create table kb_documents (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  source_file_id uuid references files(id),
  title text not null,
  source_url text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index kb_documents_tenant_idx on kb_documents(tenant_id);

create trigger trg_kb_documents_updated_at before update on kb_documents
  for each row execute function set_updated_at();

create table kb_chunks (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  document_id uuid not null references kb_documents(id) on delete cascade,
  chunk_index int not null,
  content text not null,
  embedding vector(1536),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (document_id, chunk_index)
);

create index kb_chunks_tenant_idx on kb_chunks(tenant_id);
create index kb_chunks_doc_idx on kb_chunks(document_id, chunk_index);
-- IVFFlat index for fast cosine similarity (built at scale)
-- create index kb_chunks_embedding_idx on kb_chunks using ivfflat (embedding vector_cosine_ops) with (lists = 100);
