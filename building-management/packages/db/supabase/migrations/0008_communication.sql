-- Building Management — Communication: bulletin, polls, conversations, notifications
-- See SPEC.md §13, §14, §15, §16, §21

create type bulletin_status as enum ('draft', 'published', 'archived');
create type poll_type as enum ('single', 'multi', 'ranked');
create type poll_eligibility as enum ('per_apartment', 'per_resident', 'owner_only', 'bill_payer_only');
create type poll_status as enum ('draft', 'open', 'closed', 'archived');

create type conv_channel as enum ('in_app', 'whatsapp', 'web_widget');
create type conv_status as enum ('open', 'pending_bot', 'pending_human', 'closed');
create type message_direction as enum ('in', 'out');
create type message_sender_type as enum ('resident', 'mgmt', 'bot', 'system');
create type message_status as enum ('queued', 'sent', 'delivered', 'read', 'failed');

create type notification_channel as enum ('push', 'email', 'sms', 'whatsapp', 'in_app');
create type notification_status as enum ('queued', 'sent', 'failed', 'read');

-- ============================================================
-- Bulletin Posts
-- ============================================================

create table bulletin_posts (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  building_id uuid not null references buildings(id) on delete cascade,
  author_user_id uuid,
  title text not null,
  body_md text not null,
  attachments jsonb not null default '[]'::jsonb,
  pinned boolean not null default false,
  pinned_until timestamptz,
  expires_at timestamptz,
  audience jsonb not null default '{"type": "all"}'::jsonb,
  reactions_enabled boolean not null default true,
  comments_enabled boolean not null default false,
  published_at timestamptz,
  status bulletin_status not null default 'draft',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index bulletin_posts_tenant_idx on bulletin_posts(tenant_id);
create index bulletin_posts_building_idx on bulletin_posts(building_id, published_at desc);
create index bulletin_posts_status_idx on bulletin_posts(tenant_id, status);
create index bulletin_posts_pinned_idx on bulletin_posts(building_id) where pinned = true;

create trigger trg_bulletin_posts_updated_at
  before update on bulletin_posts
  for each row execute function set_updated_at();

create table bulletin_reactions (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  post_id uuid not null references bulletin_posts(id) on delete cascade,
  person_id uuid not null references people(id) on delete cascade,
  emoji text not null,
  created_at timestamptz not null default now(),
  unique (post_id, person_id, emoji)
);

create index bulletin_reactions_post_idx on bulletin_reactions(post_id);

create table bulletin_comments (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  post_id uuid not null references bulletin_posts(id) on delete cascade,
  person_id uuid references people(id) on delete cascade,
  user_id uuid,
  body text not null,
  created_at timestamptz not null default now()
);

create index bulletin_comments_post_idx on bulletin_comments(post_id, created_at);

-- ============================================================
-- Polls
-- ============================================================

create table polls (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  building_id uuid not null references buildings(id) on delete cascade,
  author_user_id uuid,
  title text not null,
  description text,
  type poll_type not null default 'single',
  options jsonb not null default '[]'::jsonb,
  eligibility poll_eligibility not null default 'per_apartment',
  anonymous boolean not null default false,
  opens_at timestamptz not null default now(),
  closes_at timestamptz not null,
  requires_signature boolean not null default false,
  status poll_status not null default 'draft',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint closes_after_opens check (closes_at > opens_at)
);

create index polls_tenant_idx on polls(tenant_id);
create index polls_building_idx on polls(building_id, status);

create trigger trg_polls_updated_at
  before update on polls
  for each row execute function set_updated_at();

create table votes (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  poll_id uuid not null references polls(id) on delete cascade,
  person_id uuid references people(id), -- nullable for anonymous (use person_id_hash)
  person_id_hash text, -- HMAC for anonymous polls
  apartment_id uuid not null references apartments(id),
  choice jsonb not null,
  signature_blob text,
  ip_hash text,
  user_agent text,
  voted_at timestamptz not null default now(),
  constraint vote_identity check (
    (person_id is not null and person_id_hash is null) or
    (person_id is null and person_id_hash is not null)
  )
);

create index votes_poll_idx on votes(poll_id);
create unique index votes_per_apartment_idx on votes(poll_id, apartment_id)
  where person_id_hash is null; -- per_apartment polls: enforced at app layer when needed

-- ============================================================
-- Conversations + Messages (multi-channel inbox)
-- ============================================================

create table conversations (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  building_id uuid references buildings(id),
  person_id uuid references people(id),
  apartment_id uuid references apartments(id),
  channel conv_channel not null,
  status conv_status not null default 'open',
  assigned_user_id uuid,
  whatsapp_phone_e164 text, -- the resident's WA number used for this conv
  last_message_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index conversations_tenant_idx on conversations(tenant_id);
create index conversations_status_idx on conversations(tenant_id, status, last_message_at desc);
create index conversations_person_idx on conversations(person_id);

create trigger trg_conversations_updated_at
  before update on conversations
  for each row execute function set_updated_at();

create table messages (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  conversation_id uuid not null references conversations(id) on delete cascade,
  direction message_direction not null,
  sender_type message_sender_type not null,
  sender_user_id uuid,
  sender_person_id uuid,
  body text,
  attachments jsonb not null default '[]'::jsonb,
  whatsapp_message_id text,
  status message_status not null default 'queued',
  created_at timestamptz not null default now(),
  delivered_at timestamptz,
  read_at timestamptz
);

create index messages_conversation_idx on messages(conversation_id, created_at desc);
create unique index messages_whatsapp_id_idx on messages(whatsapp_message_id) where whatsapp_message_id is not null;

-- ============================================================
-- Bot conversations (meta per AI session)
-- ============================================================

create table bot_conversations (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  conversation_id uuid not null references conversations(id) on delete cascade,
  system_prompt_version text not null,
  tools_used jsonb not null default '[]'::jsonb,
  tokens_input bigint not null default 0,
  tokens_output bigint not null default 0,
  escalated boolean not null default false,
  escalation_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index bot_conversations_conv_idx on bot_conversations(conversation_id);

create trigger trg_bot_conversations_updated_at
  before update on bot_conversations
  for each row execute function set_updated_at();

-- ============================================================
-- Notifications
-- ============================================================

create table notifications (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  recipient_person_id uuid references people(id),
  recipient_user_id uuid,
  channel notification_channel not null,
  template_key text not null,
  payload jsonb not null default '{}'::jsonb,
  status notification_status not null default 'queued',
  provider_message_id text,
  dedupe_key text,
  scheduled_for timestamptz not null default now(),
  sent_at timestamptz,
  read_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index notifications_tenant_status_idx on notifications(tenant_id, status, scheduled_for);
create index notifications_recipient_idx on notifications(recipient_person_id) where recipient_person_id is not null;
create unique index notifications_dedupe_idx on notifications(tenant_id, dedupe_key) where dedupe_key is not null;

create trigger trg_notifications_updated_at
  before update on notifications
  for each row execute function set_updated_at();
