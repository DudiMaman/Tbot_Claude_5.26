-- Building Management — Flyers, KB documents, and a few helper indexes.

create type flyer_variant as enum ('a4_print', 'instagram_square', 'whatsapp_story', 'generic_image');

create table flyers (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  building_id uuid not null references buildings(id) on delete cascade,
  variant flyer_variant not null,
  qr_payload text not null,
  pdf_file_id uuid,
  image_file_id uuid,
  generated_at timestamptz not null default now(),
  unique (building_id, variant)
);

create index flyers_tenant_idx on flyers(tenant_id);

alter table flyers enable row level security;
create policy flyers_tenant on flyers for all
  using (tenant_id = current_tenant_id()) with check (tenant_id = current_tenant_id());
