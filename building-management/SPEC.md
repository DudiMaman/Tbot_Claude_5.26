# Plan: Israeli Building-Management SaaS CRM — Master Specification

## Context

This document is the master, end-to-end specification for a greenfield Israeli SaaS CRM platform for building management companies (חברות ניהול ואחזקת מבנים). It is written to be handed directly to Claude Code, which will implement every module, screen, table, and integration described below without further architectural guesswork.

The product replicates and exceeds three competitors:

- **Darimpo** (chat-first maintenance, AI assistant, multi-building map).
- **Bllink** (HOA fintech: recurring tenant charges, installments, vendor payouts, line of credit).
- **Build-app** (va'ad bayit super-app: parking gates, polls, petty cash, broadcasts).

Beyond parity, we add: welcome flyer generation with QR onboarding, management-company-driven recurring tenant billing (not just va'ad bayit), WhatsApp-native customer service, an AI bot (Claude `claude-sonnet-4-6`), bulletin board, addon-products marketplace, and a Hebrew-RTL marketing site with dashboard aesthetic.

The repository currently in `/home/user/Tbot_Claude_5.26` is an unrelated Python trading bot. The CRM is built greenfield in a new monorepo described in §29.

Technology decisions are fixed:

- **Mobile**: React Native + Expo SDK 51, single codebase iOS+Android (+ web export).
- **Backend**: Node.js 20 LTS + NestJS 10 + TypeScript 5 (modular monolith).
- **DB / Infra**: Postgres 15 via Supabase (region `eu-west-1`); Supabase Auth, Storage, Realtime, Row-Level Security (RLS).
- **Payments**: Tranzila (Israeli PSP) — tokenization, recurring charges, refunds, installments, J5/J4.
- **AI**: Anthropic Claude, model `claude-sonnet-4-6`.
- **WhatsApp**: Meta WhatsApp Business Cloud API (direct).
- **Multi-tenancy**: shared DB, `tenant_id` column on every row, Postgres RLS for isolation.
- **Marketing site + admin web**: Next.js 14 (App Router) + TS + Tailwind + shadcn/ui, full Hebrew RTL.

Throughout the document, "tenant" without qualification means *management-company tenant* in the SaaS multi-tenancy sense (i.e., one customer of our SaaS). The English term for the person living in an apartment is "resident" (Hebrew: דייר).

A critical domain nuance — Israeli rentals frequently separate the **registered owner** of an apartment from the **renter who actually pays the va'ad fees**. The platform must support this first-class (see §3.6).

---

## 1. Executive Summary

### Vision

A single, modern, Hebrew-first SaaS that lets an Israeli building-management company run its entire business — operations, finance, communication, and governance — from one platform. Residents get a phone app that feels like a consumer fintech product; maintenance workers get a Waze-grade field app; the management company gets a Linear-grade back office and a desktop client.

### Positioning

| Competitor | Their wedge | Our answer |
|---|---|---|
| Darimpo | Chat + AI ops assistant | We embed Claude `claude-sonnet-4-6` natively, tool-enabled, multi-channel. |
| Bllink | Recurring HOA collection | We do collection AND task ops AND comms in one platform; no extra integrations. |
| Build-app | Va'ad bayit gadgets (gate, polls) | We include all of it AND are management-company-grade, not just per-building. |

### Why we win

1. **Single platform** for management company, resident, owner, and worker. No swivel-chair.
2. **WhatsApp + AI bot** as first-class channels (Israelis live on WhatsApp).
3. **Hebrew RTL everywhere**, accountant-grade Israeli receipts, Masav payout files.
4. **Welcome flyer generator** drives resident activation from day one.
5. **First-class owner ↔ renter ↔ bill-payer model** — competitors treat the resident as a single actor; we model the real-world separation.
6. **Modern stack** lets a small team ship and operate it.

### Acceptance criteria

- A new prospect can sign up on the marketing site, create a building, generate a flyer, distribute it, and within 24 hours residents are paying via the app.
- 95% of a management company's daily operations can be done without leaving the platform.

---

## 2. System Architecture Overview (C4)

### 2.1 Context (Level 1)

External actors:

- **Marketing visitor** → Marketing site (Next.js).
- **Management user** (admin/member) → Admin Web (Next.js) or Desktop (Electron wrapper of Admin Web).
- **Resident / Owner / Renter** → Resident Mobile (Expo RN) + WhatsApp + Web widget.
- **Maintenance worker** → Maintenance Mobile (Expo RN).
- **Tranzila** → inbound webhooks (payment events) + outbound API.
- **Meta WhatsApp Cloud API** → inbound webhooks (messages) + outbound API.
- **Anthropic API** → outbound (Claude completions + tool use).
- **Email/SMS providers** (Resend, Inforu) → outbound.
- **Banks / Israeli accounting SaaS** (Hashavshevet, Rivhit, Priority, Wizcount, Masav files).

### 2.2 Container (Level 2)

```
                +-----------------------------+
                |   Marketing Site (Next.js)  |  vercel.app -> custom domain
                +--------------+--------------+
                               |
                               v (CTA -> signup)
+----------+        +----------------------+        +------------------+
| Resident |<--+    |  Admin Web (Next.js) |<------>|  Desktop (Elec.) |
|  Mobile  |   |    +----------+-----------+        +------------------+
|  (Expo)  |   |               |
+-----+----+   |               v
      |        |    +-----------------------------+
      v        +--->|     NestJS API (Node 20)    |<--- WhatsApp webhook
+----------+        |  - REST + tRPC + WebSocket  |<--- Tranzila webhook
|Maintenance|------>|  - BullMQ workers           |
| Mobile   |        |  - AI worker (Claude)       |
| (Expo)   |        +------+--------+-------+-----+
+----------+               |        |       |
                           v        v       v
                  +--------+--+ +---+---+ +-+-------+
                  | Postgres  | | Redis | | Storage |
                  | (Supabase)| | (BullMQ)| (Supabase)
                  +-----------+ +-------+ +---------+
                       ^
                       | (Supabase Auth, Realtime, RLS)
                       |
                  +----+----------+
                  | Supabase Auth |
                  +---------------+
```

### 2.3 Component (Level 3, inside NestJS API)

Modules (each a NestJS `@Module`):

- `AuthModule` — Supabase JWT validation, role resolution, RLS-context guard.
- `TenantsModule` — management-company CRUD, plan/quotas.
- `BuildingsModule` — buildings, addresses, geo, settings.
- `ApartmentsModule` — units, sizes, **assignments (owner/renter/bill-payer)**.
- `PeopleModule` — master person records (PII); claim flow; phone-matching.
- `WorkersModule` — maintenance staff; skills; availability.
- `TasksModule` — planned + reactive, Kanban/calendar/map.
- `TicketsModule` — resident intake + triage + status.
- `BillingModule` — schedules, charges, **bill-payer resolution**, retries, dunning.
- `PaymentsModule` — Tranzila integration, tokens, refunds.
- `VendorsModule` — directory, invoices, payouts, Masav.
- `BulletinModule` — posts, pins, audience, reactions.
- `PollsModule` — polls + digital form signing (owner-weighted vs renter rules).
- `WhatsAppModule` — inbound webhook + outbound + templates.
- `AiBotModule` — Claude completions + tool registry.
- `FlyersModule` — PDF + share variants + QR.
- `AddonsModule` — catalog + purchase + commission.
- `AccessModule` — parking gates + guest codes.
- `NotificationsModule` — fan-out across push/email/SMS/WhatsApp.
- `ReportsModule` — analytics, export.
- `AuditModule` — immutable audit trail.
- `FilesModule` — Supabase Storage signed URLs.

Shared cross-cutting: `LoggerModule` (Pino), `MetricsModule` (Prom client), `QueueModule` (BullMQ), `ConfigModule` (Zod-validated env).

### Acceptance criteria

- Architecture diagram renders cleanly from this text in any C4-aware tool.
- Every external integration has exactly one owning module.
- No module reaches into another module's data layer; they call services or emit events.

---

## 3. Domain Model

All entities below carry: `id uuid pk`, `tenant_id uuid not null` (except `Tenant` itself), `created_at timestamptz default now()`, `updated_at timestamptz`, `deleted_at timestamptz null` (soft delete where noted).

### 3.1 Core entities

**Tenant** (= management company)
`name, legal_name, vat_id (ח.פ./עוסק מורשה), billing_email, plan (enum: trial/starter/pro/enterprise), trial_ends_at, locale (default he-IL), timezone (default Asia/Jerusalem), branding_json (logo url, primary color), features_json (feature flags), status (active/suspended)`.

**Building**
`tenant_id, name, address_line, city, postal_code, geo_lat, geo_lng, num_floors, num_apartments, year_built, bank_account_iban (per-building escrow), notes, settings_json, claim_secret (used in flyer QR)`.

**Apartment**
`tenant_id, building_id, unit_number, floor, size_sqm, num_rooms, occupancy_status (vacant/owner_occupied/rented/mixed), monthly_dues_amount, current_bill_payer_assignment_id (denormalized for fast billing), notes`.

**Person** (master PII record — one human, regardless of how many apartments they relate to)
`tenant_id, full_name, id_number_encrypted, phone_e164, email, language (he/en/ru/ar), push_token, whatsapp_opt_in, supabase_user_id (nullable until they install the app), claim_status (pending/approved/rejected), claim_method (qr/manual/auto_phone/invited_by_owner)`.

A `Person` may be linked to **zero, one, or many** apartments via `ApartmentAssignment` (§3.6).

**ManagementUser**
`tenant_id, full_name, email, phone_e164, role (mgmt_admin/mgmt_member), permissions_json, supabase_user_id, last_login_at`.

**MaintenanceWorker**
`tenant_id, full_name, phone_e164, email, skills_json (array of enums: plumbing, electrical, hvac, locksmith, general), employment_type (employee/contractor), hourly_rate, supabase_user_id, status (active/inactive)`.

**Task**
`tenant_id, building_id, apartment_id (nullable), source (planned/ticket/adhoc), source_ticket_id (nullable), title, description_md, category, priority (low/med/high/urgent), assigned_worker_id (nullable), scheduled_at, sla_due_at, started_at, completed_at, status (todo/in_progress/blocked/done/cancelled), checklist_json, time_spent_minutes, cost_amount, customer_visible (bool)`.

**ServiceTicket**
`tenant_id, building_id, apartment_id, opened_by_person_id, intake_channel (app/whatsapp/bot/phone/walkin), title, description, category (auto-classified), photos_json (array of file ids), videos_json, status (new/triaged/assigned/in_progress/pending_parts/resolved/closed), assigned_task_id, sla_due_at, satisfaction_rating, resolution_note, opened_at, resolved_at, closed_at`.

> NOTE: `opened_by_person_id` (not `resident_id`) — see §3.6. Either the owner or the renter may open a ticket; the system records who and notifies all relevant parties per the apartment's notification policy.

### 3.2 Billing entities

**ChargeSchedule**
`tenant_id, building_id, apartment_id (nullable when whole-building), name, amount, currency (ILS), cadence (one_off/monthly/quarterly/annual), start_date, end_date (nullable), day_of_month (for monthly), installments_allowed (int 0..12), bill_payer_rule (enum: current_bill_payer/specific_person_id/owner/primary_occupant), bill_payer_person_id (nullable, used when rule=specific_person_id), status (active/paused/ended)`.

**Charge**
`tenant_id, building_id, apartment_id, billed_to_person_id (resolved at cycle time from rule above), schedule_id (nullable), description, amount, currency, due_date, status (pending/paid/partial/overdue/cancelled/refunded), invoice_number, vat_amount, paid_amount, last_reminder_at, dunning_stage (0..5)`.

**Payment**
`tenant_id, charge_id, paid_by_person_id (may differ from billed_to_person_id — e.g., owner covers for renter), method (card/cash/check/wire/other), amount, currency, status (pending/captured/failed/refunded), tranzila_token_id (nullable), tranzila_txn_id, last4, brand (visa/mc/amex/isracard/leumicard), installments (1..12), captured_at, failure_reason, raw_provider_json`.

**PaymentMethod**
`tenant_id, owner_person_id, type (card), tranzila_token, brand, last4, expiry_month, expiry_year, is_default, status (active/expired/removed)`.

### 3.3 Vendor entities

**Vendor**
`tenant_id, name, contact_name, phone, email, vat_id, iban, services_json, rating, notes, status`.

**VendorInvoice**
`tenant_id, vendor_id, building_id, invoice_number, issue_date, due_date, amount, vat_amount, currency, file_id, status (received/approved/scheduled/paid/rejected), approver_id, notes`.

**VendorPayout**
`tenant_id, vendor_id, invoice_ids (array), amount, method (tranzila/masav/wire), masav_file_id (nullable), scheduled_for, executed_at, status (scheduled/sent/confirmed/failed), reference_number`.

### 3.4 Communication entities

**BulletinPost**
`tenant_id, building_id, author_user_id, title, body_md, attachments_json, pinned (bool), pinned_until, expires_at, audience_json (all/apartment_ids/group_tag/role_in_apt), reactions_enabled, comments_enabled, published_at, status (draft/published/archived)`.

**Poll**
`tenant_id, building_id, author_user_id, title, description, type (single/multi/ranked), options_json, eligibility (per_apartment/per_resident/owner_only/bill_payer_only), anonymous (bool), opens_at, closes_at, requires_signature (bool), status`.

**Vote** — `poll_id, person_id (hashed when anonymous), apartment_id, choice_json, signature_blob, ip_hash, user_agent, voted_at`.

**Announcement** — broadcast message; `audience_json, channels_json (push/email/sms/whatsapp), title, body, scheduled_for, sent_at, stats_json`.

**Conversation** (multi-channel inbox)
`tenant_id, building_id (nullable), person_id (nullable), apartment_id (nullable), channel (in_app/whatsapp/web_widget), status (open/pending_bot/pending_human/closed), assigned_user_id, last_message_at`.

**Message**
`conversation_id, direction (in/out), sender_type (resident/mgmt/bot/system), body, attachments_json, whatsapp_message_id, status (queued/sent/delivered/read/failed), created_at`.

**BotConversation** — `conversation_id, system_prompt_version, tools_used_json, tokens_input, tokens_output, escalated (bool), escalation_reason`.

### 3.5 Misc entities

**Flyer** — `tenant_id, building_id, variant (a4_print/instagram_square/whatsapp_story/generic_image), qr_payload, pdf_file_id, image_file_id, generated_at`.

**AddonProduct** — `tenant_id, sku, name, description, price, currency, vat_inclusive, availability_buildings (array), inventory (nullable), commission_pct, image_file_id, status`.

**AddonOrder** — `tenant_id, product_id, ordered_by_person_id, building_id, apartment_id, qty, total, payment_id, fulfillment_status (pending/in_progress/delivered/cancelled), notes`.

**AccessGate** — `tenant_id, building_id, name, kind (parking/pedestrian), provider (http_webhook/mqtt/sesame/custom), config_json, status`.

**AccessEvent** — `gate_id, person_id (nullable), guest_code_id (nullable), action (open/deny), source (app/code/manual), created_at`.

**GuestCode** — `tenant_id, building_id, gate_id, code, created_by_person_id, valid_from, valid_to, max_uses, uses, status`.

**AuditLog** — `tenant_id, actor_user_id, actor_type, action (verb), entity_type, entity_id, before_json, after_json, ip, user_agent, created_at` (append-only).

**Notification** — `tenant_id, recipient_person_id, channel, template_key, payload_json, status (queued/sent/failed/read), provider_message_id, scheduled_for, sent_at, read_at`.

**File** — `tenant_id, owner_user_id, bucket, path, mime, size, sha256, pii_tag (none/pii/financial), virus_scan_status`.

### 3.6 Ownership vs Occupancy vs Billing — first-class domain (CRITICAL)

The Israeli market commonly has an apartment with a **registered owner** who does not live there, while a **renter** lives in the unit and is the one paying the building fees (per the rental contract). The platform models this explicitly. Competitors collapse "resident" into one role; we do not.

#### 3.6.1 Concepts

- **Person** — a human. PII lives here exactly once per tenant.
- **Apartment** — a physical unit.
- **ApartmentAssignment** — a time-bounded link between a Person and an Apartment with a specific role and flags.

#### 3.6.2 `ApartmentAssignment` entity

```
ApartmentAssignment
  id                  uuid pk
  tenant_id           uuid
  apartment_id        uuid fk
  person_id           uuid fk
  role                enum (owner | renter | family_member | authorized_contact)
  is_primary          boolean        -- one primary per (apartment, role) at a time
  is_occupant         boolean        -- "does this person live in the unit"
  is_bill_payer       boolean        -- "this person is responsible for va'ad fees"
  share_pct           numeric(5,2)   -- for split ownership/payment (sum per apartment ≤ 100)
  valid_from          date
  valid_to            date nullable  -- null = open-ended (current)
  rental_contract_id  uuid nullable  -- when role=renter, links to RentalContract
  notes               text
  status              enum (active | ended | superseded)
  created_at, updated_at, deleted_at
```

Constraints (DB-enforced + service-validated):

- Exactly **zero or one** assignment per apartment with `is_bill_payer = true` and `valid_to is null` (the "current bill payer"). Enforced via partial unique index:
  ```sql
  create unique index one_current_bill_payer_per_apt
    on apartment_assignments(apartment_id)
    where is_bill_payer = true and valid_to is null and status = 'active';
  ```
- At most one `is_primary = true` per `(apartment_id, role)` with `valid_to is null`.
- `share_pct` sums to ≤ 100 per apartment for active owner assignments (warning, not hard-fail).
- A `renter` assignment must have `is_occupant = true` (renters always occupy).
- An `owner` may have any combination of `is_occupant` and `is_bill_payer` (owner-occupier, absentee owner, or owner who pays while renter lives there).

#### 3.6.3 `RentalContract` entity

```
RentalContract
  id, tenant_id
  apartment_id
  owner_person_id          -- landlord
  renter_person_id         -- tenant of the apartment
  start_date, end_date
  monthly_rent             numeric(12,2) nullable (informational)
  va'ad_responsibility     enum (renter_pays | owner_pays | split)
  split_renter_pct         numeric(5,2) nullable
  contract_file_id         uuid nullable
  status                   enum (draft | active | ended | terminated)
  created_at, updated_at
```

When a `RentalContract` becomes `active`, the system writes/updates `ApartmentAssignment`s automatically:
- The owner's existing assignment is updated: `is_bill_payer` flipped based on `va'ad_responsibility`.
- The renter's assignment is created with `role=renter, is_occupant=true, is_bill_payer=(va'ad_responsibility=renter_pays)`.

#### 3.6.4 Bill-payer resolution algorithm (used by BillingModule)

When a `Charge` is generated by a `ChargeSchedule`:

```
function resolveBillPayer(apartmentId, scheduleRule, asOfDate):
  switch scheduleRule:
    case 'specific_person_id':
      return schedule.bill_payer_person_id  // override
    case 'owner':
      return apartment.assignments
        .filter(a => a.role == 'owner' && a.is_primary && active(a, asOfDate))
        .first().person_id
    case 'primary_occupant':
      return apartment.assignments
        .filter(a => a.is_occupant && a.is_primary && active(a, asOfDate))
        .first().person_id
    case 'current_bill_payer' (DEFAULT):
      return apartment.assignments
        .filter(a => a.is_bill_payer && active(a, asOfDate))
        .first().person_id
      // fallback if no bill_payer set:
      //   -> primary owner; if none -> any owner; if none -> primary occupant
      //   -> if none, flag charge.status = 'unbilled_no_payer' and notify mgmt
```

Resolution happens at **cycle generation time** and is recorded on `Charge.billed_to_person_id` (immutable for that charge — historical accuracy). Changes after generation do not retroactively re-route already-generated charges; they affect future cycles only.

#### 3.6.5 Permissions implications

Per-person, per-apartment effective permissions (resolved at JWT mint time, refreshed on assignment change):

| Capability | Owner (occupant) | Owner (absentee) | Renter (bill_payer) | Renter (not bill_payer) | Family member |
|---|---|---|---|---|---|
| View own charges | ✅ (their charges) | ✅ (their charges) | ✅ (their charges) | ❌ | ❌ |
| Pay charge | ✅ | ✅ | ✅ | ❌ | ❌ |
| View apartment-wide charge history (all payers ever) | ✅ | ✅ | ❌ (only their own) | ❌ | ❌ |
| Open service ticket | ✅ | ✅ (in-app + notified) | ✅ | ✅ | ✅ |
| Receive maintenance updates | ✅ | optional (per pref) | ✅ | ✅ | ✅ |
| Vote in polls (eligibility) | ✅ when rule=owner_only or per_apartment | ✅ when rule=owner_only | ✅ when rule=per_resident or bill_payer_only | ✅ when rule=per_resident | ❌ |
| Generate guest gate code | ✅ (occupant) | ❌ | ✅ | ✅ | ✅ |
| See bulletin board | ✅ | optional (per pref) | ✅ | ✅ | ✅ |
| Edit apartment details | ❌ (mgmt only) | ❌ | ❌ | ❌ | ❌ |
| Manage rental contract | ✅ (owner) | ✅ (owner) | view-only | ❌ | ❌ |
| Invite another person to apartment | ✅ owner can invite renter/family | ✅ | ✅ family member only | ❌ | ❌ |

#### 3.6.6 Notification routing

For each apartment-scoped notification, the engine fans out per the apartment's `notification_policy`:

```
notification_policy (per Apartment, default by tenant):
{
  charge_due:         ["bill_payer"]                  // typically renter
  charge_overdue:     ["bill_payer", "owner"]         // copy owner if renter is late
  ticket_update:      ["opener", "all_occupants"]
  bulletin:           ["all_occupants", "owner_if_absentee"]  // owner can opt-out
  maintenance_entry:  ["all_occupants", "owner"]      // legal access notice
  poll_open:          ["eligible_voters_per_rule"]
}
```

This policy is editable per-apartment by mgmt, and resolves to a set of `recipient_person_id`s at fanout time.

#### 3.6.7 Onboarding flows for the 3 cases

**Case A — Owner-occupant (lives there, pays):**
1. Owner scans QR (or invited by mgmt).
2. Claims apartment as owner; sets `is_occupant=true, is_bill_payer=true, is_primary=true`.
3. Done.

**Case B — Renter pays, owner is absentee:**
1. Mgmt or owner creates a `RentalContract` with `va'ad_responsibility = renter_pays`.
2. Mgmt enters renter's phone + name; sends invite SMS.
3. Renter installs app, OTP-claims; assignment auto-created with `is_bill_payer=true`.
4. Owner keeps their assignment but `is_bill_payer=false, is_occupant=false`. Owner still receives copies of overdue notices.

**Case C — Owner pays, renter occupies:**
1. Same as B but `va'ad_responsibility = owner_pays`.
2. Renter is added with `is_bill_payer=false`; can still open tickets and receive comms, but charges route to owner.

**Case D — Split (rare):**
1. `va'ad_responsibility = split` with `split_renter_pct = 50`.
2. Each `ChargeSchedule` produces two `Charge` rows on cycle day: one for owner with 50%, one for renter with 50%. Receipts are independent.

#### 3.6.8 Migration / lifecycle

- **New renter moves in (mid-contract)**: end old `RentalContract`; create new; old renter's assignment gets `valid_to = today, status = ended`; new renter's assignment created. Past charges remain billed to the prior payer.
- **Owner sells the apartment**: mgmt records the sale; old owner's assignment `status=ended`; new owner invited; pending charges (already generated) remain on the previous bill_payer unless mgmt explicitly reassigns.
- **Vacancy**: when no active assignment exists, `apartments.occupancy_status='vacant'`; charges either continue against the owner (if owner assignment active) or pause (`schedule.bill_payer_rule=current_bill_payer` + no payer → `charge.status=unbilled_no_payer`).

### Acceptance criteria (§3)

- Every entity above maps 1:1 to a Postgres table in §4.
- Every entity carries `tenant_id` (except `Tenant`).
- Soft delete is supported on Building, Apartment, Person, ManagementUser, MaintenanceWorker, Vendor, AddonProduct.
- The three rental scenarios (A/B/C/D) are fully covered by `ApartmentAssignment` + `RentalContract` with no app-level workarounds.
- Negative test: creating two active `is_bill_payer=true` rows for the same apartment fails at the DB layer.

---

## 4. Postgres Schema (DDL outline)

Schema lives in `packages/db/migrations/` as Supabase migration SQL files. Prisma generates a typed client into `packages/db/prisma`. Where Prisma and Supabase migrations conflict, **Supabase SQL is the source of truth**; Prisma `db pull` after migrations.

### 4.1 Conventions

- All ids: `uuid` default `gen_random_uuid()`.
- All money: `numeric(12,2)`.
- All timestamps: `timestamptz`.
- Enum types declared in `public` schema: `tenant_plan`, `user_role`, `task_status`, `ticket_status`, `charge_status`, `payment_status`, `payment_method`, `channel`, `conversation_status`, `dunning_stage`, `apartment_role`, `bill_payer_rule`, `vaad_responsibility`, etc.
- Every table gets `(tenant_id)` and `(tenant_id, created_at desc)` indexes minimum.

### 4.2 Selected DDL (representative — Claude Code generates the rest from §3 by the same pattern)

```sql
create extension if not exists pgcrypto;
create extension if not exists postgis;

create type tenant_plan        as enum ('trial','starter','pro','enterprise');
create type user_role          as enum ('mgmt_admin','mgmt_member','maintenance','resident');
create type apartment_role     as enum ('owner','renter','family_member','authorized_contact');
create type bill_payer_rule    as enum ('current_bill_payer','specific_person_id','owner','primary_occupant');
create type vaad_responsibility as enum ('renter_pays','owner_pays','split');

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
  features  jsonb not null default '{}'::jsonb,
  status text not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table buildings (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  name text not null,
  address_line text not null,
  city text not null,
  postal_code text,
  geo geography(point,4326),
  num_floors int,
  num_apartments int,
  year_built int,
  bank_account_iban text,
  claim_secret text not null default encode(gen_random_bytes(16),'hex'),
  notes text,
  settings jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);
create index on buildings (tenant_id);
create index on buildings using gist (geo);

create table apartments (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  building_id uuid not null references buildings(id) on delete cascade,
  unit_number text not null,
  floor int,
  size_sqm numeric(8,2),
  num_rooms numeric(3,1),
  occupancy_status text not null default 'vacant',
  monthly_dues_amount numeric(12,2),
  notification_policy jsonb not null default '{}'::jsonb,
  notes text,
  unique (building_id, unit_number),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);
create index on apartments (tenant_id, building_id);

create table people (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  full_name text not null,
  id_number_encrypted bytea,
  phone_e164 text,
  email text,
  language text default 'he',
  push_token text,
  whatsapp_opt_in boolean default false,
  claim_status text default 'pending',
  claim_method text,
  supabase_user_id uuid unique,
  notification_prefs jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);
create index on people (tenant_id, phone_e164);
create unique index on people (tenant_id, supabase_user_id) where supabase_user_id is not null;

create table apartment_assignments (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  apartment_id uuid not null references apartments(id) on delete cascade,
  person_id uuid not null references people(id) on delete cascade,
  role apartment_role not null,
  is_primary boolean not null default false,
  is_occupant boolean not null default false,
  is_bill_payer boolean not null default false,
  share_pct numeric(5,2),
  valid_from date not null default current_date,
  valid_to date,
  rental_contract_id uuid,
  notes text,
  status text not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index on apartment_assignments (tenant_id, apartment_id) where status='active' and valid_to is null;
create index on apartment_assignments (tenant_id, person_id);
create unique index one_current_bill_payer_per_apt
  on apartment_assignments(apartment_id)
  where is_bill_payer = true and valid_to is null and status = 'active';
create unique index one_primary_per_role_per_apt
  on apartment_assignments(apartment_id, role)
  where is_primary = true and valid_to is null and status = 'active';

create table rental_contracts (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  apartment_id uuid not null references apartments(id) on delete cascade,
  owner_person_id uuid not null references people(id),
  renter_person_id uuid not null references people(id),
  start_date date not null,
  end_date date,
  monthly_rent numeric(12,2),
  vaad_responsibility vaad_responsibility not null default 'renter_pays',
  split_renter_pct numeric(5,2),
  contract_file_id uuid,
  status text not null default 'draft',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table charge_schedules (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  building_id uuid not null references buildings(id),
  apartment_id uuid references apartments(id),
  name text not null,
  amount numeric(12,2) not null,
  currency text not null default 'ILS',
  cadence text not null,
  day_of_month int,
  start_date date not null,
  end_date date,
  installments_allowed int not null default 1,
  bill_payer_rule bill_payer_rule not null default 'current_bill_payer',
  bill_payer_person_id uuid references people(id),
  status text not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table charges (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  building_id uuid not null references buildings(id),
  apartment_id uuid not null references apartments(id),
  billed_to_person_id uuid references people(id),
  schedule_id uuid references charge_schedules(id),
  description text,
  amount numeric(12,2) not null,
  currency text not null default 'ILS',
  due_date date not null,
  status text not null default 'pending',
  invoice_number text,
  vat_amount numeric(12,2),
  paid_amount numeric(12,2) not null default 0,
  last_reminder_at timestamptz,
  dunning_stage int not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index on charges (tenant_id, status, due_date);
create index on charges (tenant_id, billed_to_person_id, status);
```

The same shape continues for every entity in §3. Claude Code must produce the full DDL during M0/M1.

### 4.3 RLS pattern (mandatory on every tenant-scoped table)

```sql
alter table buildings enable row level security;

create policy tenant_isolation_select on buildings
  for select using (tenant_id = (auth.jwt()->>'tenant_id')::uuid);

create policy tenant_isolation_modify on buildings
  for all using   (tenant_id = (auth.jwt()->>'tenant_id')::uuid)
           with check (tenant_id = (auth.jwt()->>'tenant_id')::uuid);
```

Resident-scoped tables get an additional policy: a resident may only see rows where the apartment is referenced by an `apartment_assignments` row with their `person_id` and `status='active'`. Example for `charges`:

```sql
create policy resident_own_apartment_charges on charges
  for select using (
    (auth.jwt()->>'role') = 'resident' and exists (
      select 1 from apartment_assignments aa
      where aa.apartment_id = charges.apartment_id
        and aa.person_id = ((auth.jwt()->>'person_id')::uuid)
        and aa.status = 'active'
        and (aa.valid_to is null or aa.valid_to >= current_date)
    )
  );

-- AND: bill payer / occupant-specific further restrictions enforced in service layer
-- (e.g., a renter who is not bill_payer cannot see charges where billed_to_person_id != self)
```

Maintenance workers see only buildings they're assigned to (via `worker_building_assignments` table).

### 4.4 Indexes baseline

- `charges (tenant_id, status, due_date)` — dunning queries.
- `charges (tenant_id, billed_to_person_id, status)` — per-person AR.
- `apartment_assignments (tenant_id, apartment_id) where status='active' and valid_to is null` — current state.
- `tickets (tenant_id, status, sla_due_at)` — SLA dashboard.
- `tasks (tenant_id, assigned_worker_id, scheduled_at)` — worker day plan.
- `messages (conversation_id, created_at desc)`.
- `audit_log (tenant_id, entity_type, entity_id, created_at desc)`.

### Acceptance criteria

- `pnpm db:migrate` applies cleanly on a fresh Supabase project.
- `pnpm db:seed` produces a demo tenant with 2 buildings, 30 apartments, 50 people, including: (a) one owner-occupant apartment, (b) one rented apartment where renter pays, (c) one rented apartment where owner pays, (d) one split case.
- `select * from buildings` returns 0 rows when JWT `tenant_id` is unset (RLS proven).
- Attempting to insert a second `is_bill_payer=true` active row for the same apartment raises `unique_violation`.

---

## 5. Authentication & Authorization

### 5.1 Supabase Auth setup

- Use Supabase Auth with **email + password**, **phone + OTP** (Israeli numbers), and **magic-link email** providers enabled.
- App users live in `auth.users`; each domain user table (`management_users`, `maintenance_workers`, `people`) has `supabase_user_id uuid unique references auth.users(id)`.
- **First login: role + tenant assignment.** A Postgres function `handle_new_auth_user()` is wired as an `AFTER INSERT` trigger on `auth.users`. It inspects `raw_user_meta_data->>'invite_token'`:
  - If present and valid → links to the right `management_users` / `maintenance_workers` / `people` row and sets `tenant_id`.
  - Else → creates a stub `pending_user` row for manual claim.

### 5.2 JWT claims

Custom claims added via Supabase Auth hook (Edge Function):
```
{
  "sub": "<auth.users.id>",
  "tenant_id": "<uuid>",
  "role": "mgmt_admin | mgmt_member | maintenance | resident",
  "person_id": "<uuid|null>",         // for resident
  "building_ids": ["<uuid>", ...],    // for maintenance + resident
  "apartment_ids": ["<uuid>", ...],   // resident may have multiple (e.g., owner of 3 apts)
  "permissions": ["billing.write", ...] // mgmt_member only
}
```

`apartment_ids` is the union of all active assignments; per-apartment role/flags are read on demand via `apartment_assignments`.

### 5.3 NestJS guard

`SupabaseJwtGuard` validates JWT with Supabase JWKS; `RlsContextInterceptor` sets `set local request.jwt.claims = '...'` on the PG connection for the request (so RLS policies fire on the API path too, not only on PostgREST).

### 5.4 Roles & permissions

- `mgmt_admin` — full tenant access.
- `mgmt_member` — fine-grained permissions: `billing.read`, `billing.write`, `tasks.write`, `tickets.write`, `vendors.write`, `comms.write`, `reports.read`. Set in `management_users.permissions_json`.
- `maintenance` — read assigned buildings; write own tasks; write own ticket replies.
- `resident` — read/write per §3.6.5 effective permissions matrix.

### 5.5 Invitation flow (mgmt + worker)

`POST /v1/invitations` → creates `invitations(token, tenant_id, role, email, expires_at)`. Sends email/SMS deep link `https://app.<domain>/accept?token=...`. Page exchanges token → Supabase signUp → trigger consumes invite → user is bound. Token TTL 7 days, single use.

### 5.6 Resident QR onboarding

Each Building has a stable `claim_secret`. Flyer QR encodes deep link:
```
https://app.<domain>/claim?b=<building_id>&s=<claim_secret>
```
Resident installs Expo app → universal link opens claim screen → phone OTP via Supabase → enters unit number + name + role (owner / renter / family) → matched against `apartments`; if `people.phone_e164` already exists with this phone, auto-link; else create `pending` person row → mgmt approves in admin → push notification to resident.

### 5.7 Owner invites renter / family flow

In the resident app, an owner sees their apartments with an "Invite person to this apartment" action. They select role (renter / family_member), enter phone + name. The system creates a `pending` `Person` + `ApartmentAssignment` (status `pending`) and sends an SMS invite. The owner's invitation requires mgmt approval if the role is `renter` (to prevent unauthorized rentals); `family_member` invites are auto-approved with mgmt visibility.

### Acceptance criteria

- A user with `role=resident` cannot `select` any row from another resident's apartment via either REST API or direct PostgREST call. Negative test included in CI.
- A management user invited via email completes signup and lands on the admin dashboard within 60 seconds, with `tenant_id` already set on JWT.
- A renter cannot view charge history of charges billed to the prior tenant of the same apartment.

---

## 6. Marketing Website

Path: `apps/marketing` (Next.js 14 App Router).

### 6.1 Sitemap

- `/` (Home) — hero + value props + product preview + CTA.
- `/features` — full features grid, anchored sub-sections per module.
- `/who-its-for` — segmented: management companies / large vs small / va'ad bayit option.
- `/pricing` — tiered pricing table + ROI calculator.
- `/testimonials`.
- `/blog` — MDX-based; Hebrew posts about HOA management.
- `/faq`.
- `/contact` — form posts to `/api/lead`.
- `/legal/terms`, `/legal/privacy`, `/legal/dpa`.
- `/he` is the default; `/en` is mirrored.

### 6.2 Hero (Hebrew, RTL)

- H1: `ניהול מבנים בלי כאב ראש`
- Subhead: `פלטפורמה אחת לחברת הניהול, לדיירים, לבעלי דירות ולאנשי האחזקה`
- CTAs: `התחילו ניסיון חינם` (primary), `קבעו הדגמה` (secondary).
- Visual: animated dashboard mockup (Framer Motion).

### 6.3 Sections

- **Features**: 12-card grid. Each card = icon (lucide), Hebrew title, 1-line subtitle.
- **Who it's for**: tabs (`חברות ניהול`, `ועדי בית`, `בעלי דירות`, `דיירים שוכרים`).
- **Pricing**: 3 tiers + enterprise contact. Toggle (monthly/annual). ROI calc: inputs `# buildings`, `# apartments`, current collection rate → output savings.
- **Testimonials**: 3 quotes, real-looking placeholder.
- **FAQ**: 8 Q&A.
- **Footer**: contact, legal, social, language switcher.

### 6.4 CTA flow

`התחילו ניסיון חינם` → `/signup` (Supabase Auth signUp form) → creates tenant in `trial` plan → redirects to admin onboarding wizard.

### 6.5 SEO

- Hebrew meta tags, `lang="he"`, `dir="rtl"`.
- `next-sitemap` generates `sitemap.xml` + `robots.txt`.
- OpenGraph images via `@vercel/og`.
- Structured data: `Organization`, `Product`, `FAQPage`.
- Performance budget: LCP < 2s on Israel-region edge, CLS < 0.1.

### 6.6 Aesthetic

- Tailwind + shadcn/ui.
- Palette: indigo primary (`#4f46e5`), slate neutrals, soft gradients.
- Typography: `Heebo` (Hebrew) + `Inter` (Latin), loaded via `next/font`.
- Subtle dashboard previews using real Tailwind components, not screenshots.

### Acceptance criteria

- Lighthouse mobile ≥ 90 on all axes.
- All copy renders RTL with no layout breakage.
- Signup creates a `tenants` row and a Supabase user atomically; failure rolls back.

---

## 7. Management Company Admin (Web + Desktop)

Path: `apps/admin` (Next.js 14 App Router, behind auth). Desktop wrapper at `apps/desktop` (Electron loading `apps/admin` URL with native menu + auto-update via `electron-updater`).

### 7.1 Information architecture

Left nav (RTL: visually on the right):

```
לוח בקרה        (Dashboard)
בניינים          (Buildings)
דירות            (Apartments)
אנשים            (People — owners/renters/family)
חוזי שכירות     (Rental contracts)
משימות          (Tasks)
פניות            (Tickets)
חיובים           (Charges)
תשלומים         (Payments)
ספקים            (Vendors)
לוח מודעות      (Bulletin)
מסמכים           (Documents — per-building vault)
צ'קים            (Checks — book + bounced)
חשבוניות וקבלות (Invoices & Receipts)
סקרים            (Polls)
תקשורת           (WhatsApp inbox)
בוט AI           (AI bot tuning)
פלאיירים        (Flyer generator)
מוצרים נלווים  (Addons)
דוחות            (Reports)
הגדרות           (Settings)
לוג ביקורת      (Audit log)
```

### 7.2 Screens (wireframe-level)

**Dashboard** — KPI cards (open tickets, overdue charges, today's tasks, collection rate), recent activity feed, map widget linking to Map view, alerts (e.g., "apartment 4B has no bill payer assigned").

**Buildings list** — table + map toggle. Columns: name, address, # apartments, occupied/vacant/rented breakdown, collection rate, open tickets, financial-health badge. Filters: city, financial health, mgmt member.

**Building detail** — header (name, address, geo pin), tabs:
- *Overview* (KPIs, recent activity).
- *Apartments* (table with bulk import via CSV; columns include occupancy_status, current bill payer name, owner name).
- *People* (everyone linked to this building's apartments + claim approvals).
- *Rental contracts* (list, status, va'ad responsibility).
- *Tasks* (Kanban scoped to building).
- *Tickets* (list).
- *Charges* (schedules + outstanding).
- *Payments* (incoming).
- *Vendors used* (table).
- *Bulletin* (posts in this building).
- *Polls*.
- *Files*.
- *Settings* (per-building, including default `notification_policy`).

**Apartment detail** — assignments grid (owner / renter / family with timeline), rental contracts attached, charge history (filterable by billed person), tickets history, notes. Actions: "Add assignment", "Start rental contract", "End rental contract", "Reassign bill payer".

**People** — directory of every Person in the tenant. Click → person detail: all their apartment assignments (current + historical), their charges (paid + unpaid), their tickets, their payment methods, their conversations.

**Rental contracts** — list view, filter by status, create new (wizard), end existing.

**Tasks** — Kanban (`todo / in_progress / blocked / done`), calendar view, map view. Bulk-assign. Drag-drop changes assignee/status.

**Maintenance worker scheduling** — calendar per worker, drag tasks onto slots; conflict detection; skills matching warnings.

**Charges** —
- *Schedules* tab: create plan (per-apartment fixed, per-resident variable, one-off); choose `bill_payer_rule`; preview next 12 cycles **with resolved bill_payer names**.
- *Cycles* tab: run dry-run, run live, see retries and dunning queue.
- *Dunning* tab: configure escalation (day 0 reminder to bill_payer, day 7 SMS, day 14 WhatsApp + copy to owner, day 21 phone task, day 30 legal flag + force-notify owner).
- *Unbilled queue* — charges that couldn't resolve a bill payer (e.g., vacancy); requires mgmt action.

**Payments inbox** — unified online + offline. Reconcile checks/cash. Match to charges.

**Vendors & payouts** — directory; upload invoices; approval; schedule payout (Tranzila or Masav export).

**Bulletin manager** — rich editor (Tiptap), audience picker (with role filter: owners-only, renters-only, all), schedule/expiry, preview per channel.

**Polls** — wizard create (with eligibility selector incl. `owner_only`, `bill_payer_only`), results dashboard (live), export.

**WhatsApp inbox** — conversation list, message thread, canned replies, escalation from bot.

**AI bot tuning** — system prompt editor (versioned), tools toggle, knowledge base uploader, sandbox chat.

**Flyer generator** — pick building → preview 4 variants → download/print/share.

**Addons catalog** — product CRUD, per-building availability, fulfilment view.

**Reports** — saved reports + ad-hoc builder.

**Settings** — branding, plan/billing (the SaaS itself), team, integrations, payment provider keys, WhatsApp BSP, notification templates, locale, default `notification_policy` for new apartments.

**Audit log** — filterable timeline.

### 7.3 Desktop app specifics

- Electron 30 + `electron-builder`.
- Loads `https://admin.<domain>` in `BrowserWindow` with `nodeIntegration: false`.
- Native menu, system tray, native notifications via `Notification` API forwarded.
- Auto-update via GitHub Releases feed.

### Acceptance criteria

- Every nav item is implemented, not stubbed.
- All screens are RTL by default; English mirror works.
- The desktop app boots offline and shows a graceful reconnection banner.
- The Apartment detail screen visualizes the assignment timeline so mgmt can see who paid which charges in which periods.

---

## 8. Welcome Flyer Generator

Module: `apps/api/src/modules/flyers`. PDFs rendered server-side with `@react-pdf/renderer` + a Hebrew font (`Heebo` and `Rubik`, embedded). Share-image variants rendered via `@vercel/og` style (`satori` + `resvg`) for sharp Hebrew text.

### 8.1 Content (Hebrew)

```
ברוכים הבאים לבניין <שם הבניין>!
ניהול הבניין שלכם עבר לאפליקציה.

מה תקבלו?
• דיווח תקלות בלחיצת כפתור
• תשלום ועד בית מאובטח בכרטיס אשראי
• עדכונים מוועד הבית בזמן אמת
• בוט AI שעונה 24/7
• פתיחת שער חניה מהטלפון

סרקו את הברקוד כדי להתחיל >>>>
[QR CODE]

זקוקים לעזרה? התקשרו: <מס׳ חברת הניהול>
```

### 8.2 QR payload

```
https://app.<domain>/claim?b=<building_id>&s=<claim_secret>
```

### 8.3 Variants

- **A4 print** (PDF): full bleed, 300dpi, embedded fonts, cropmarks optional.
- **Instagram square** (PNG 1080×1080).
- **WhatsApp story** (PNG 1080×1920).
- **Generic image** (PNG 1200×630, OG-style).

### 8.4 API

`POST /v1/buildings/:id/flyer` → returns `{ pdf_url, ig_url, story_url, og_url }` (signed Supabase URLs, 7-day TTL).

### Acceptance criteria

- Hebrew glyphs render correctly (no tofu) in all four variants.
- QR scans on iPhone/Android both deep-link into the resident app's claim screen.
- Regeneration is idempotent (same building → same QR payload).

---

## 9. Resident Mobile App

Path: `apps/mobile-resident` (Expo SDK 51, RN 0.74, TypeScript). Used by **owners (occupant or absentee), renters, and family members** — UX adapts per assignment role(s).

### 9.1 Screens & flows

- **Splash** → deep-link router (`claim`, `payment-callback`, etc.).
- **Onboarding (QR / manual code)** → phone OTP → unit number + name + role picker (owner / renter / family) → submit claim → waiting / approved state.
- **Multi-apartment switcher** (top of Home) — for people with assignments to multiple apartments (common for owners with several units). Each apartment card shows current role and balance.
- **Home** — three stacks: open charges *for this apartment that you're responsible for*, open tickets, latest announcements. FAB for "new ticket".
- **Charges list / detail** — pay button → Tranzila card screen (WebView with iframe) → save card toggle → installments picker (1–12) → success / failure screen → updated balance. **Renters who are not bill_payer see "this charge is paid by the owner" placeholder** — they cannot pay it but can see status (informational).
- **Tickets list / new ticket** — category picker (with AI auto-suggest from photo), photo/video upload (Expo ImagePicker + chunked upload to Supabase Storage), description (voice-to-text supported).
- **Ticket detail** — status timeline, photos, mgmt comments, satisfaction rating on close.
- **Bulletin** — feed; pinned posts on top; reactions; comments if enabled. Filtered to posts whose audience includes the user's role for that apartment.
- **Polls** — list of active polls; vote (only if eligible per poll rule); results after close.
- **AI chat** — Claude-backed, streaming UI; falls back to human when escalated.
- **WhatsApp opt-in** — toggle to receive notifications via WhatsApp.
- **Profile** — name, language, push prefs, notification channel prefs.
- **Apartment** (visible in switcher) — role, since when, fellow residents (owner sees renter contact; renter sees owner contact when owner allows), rental contract details (read-only for renter), action: "Invite person to this apartment" (owner only).
- **Payment methods** — saved cards (tokenized), remove/replace.
- **Payment history** — list (only charges they were billed for or paid) + statement PDF download (Hebrew, accountant-grade).
- **Access** — parking gate one-tap open (occupants only); guest code generator.

### 9.2 Push notifications

- Expo Push Service. Token saved on `people.push_token`.
- Categories: `charge_due`, `ticket_update`, `announcement`, `poll_open`, `bot_reply`, `assignment_change` (e.g., new renter added by owner).
- Tap → deep link into corresponding screen.

### 9.3 Offline

- React Query persistence to AsyncStorage; mutations queue and replay.
- "Pay charge" is **never** queued offline (requires online for 3DS2).

### Acceptance criteria

- App boots in <2s on a mid-range Android.
- Full ticket flow (photo upload + submit) works on a flaky 3G connection.
- Tranzila iframe loads inside RN WebView with no CORS errors.
- A user with 3 apartment assignments can switch context and see correct data per apartment.

---

## 10. Maintenance Worker Mobile App

Path: `apps/mobile-maintenance` (same Expo monorepo, separate Expo app config).

### 10.1 Screens

- **Today** — chronological list of tasks; map view toggle.
- **Task detail** — title, description, photos, location, navigate (Waze + Google Maps deep link), check-in (button arms geofence verification if enabled), checklist tick-off, parts/materials log (free text + photo of receipts), photo before/after upload, time tracking (start/stop), mark done OR decline with reason.
- **Tickets queue** — tickets from residents that need worker reply; quick reply templates.
- **Schedule** — week view.
- **Internal chat** — with mgmt (1:1 + group per worker team).
- **Profile** — availability toggle, skills, contact mgmt.

### 10.2 Field-friendly UX

- Large tap targets, high-contrast theme, glove-friendly buttons.
- Background location only while task in progress (with explicit consent).
- Voice notes for ticket replies.

### Acceptance criteria

- Worker can complete a full task (navigate → check-in → photo → done) without typing on a hot summer day with sunlight on screen.
- All photos upload in background even if the app is backgrounded.

---

## 11. Billing & Payments Module

### 11.1 Charge plans

- **Per-apartment fixed monthly** — e.g., ₪350/month per unit.
- **Per-tenant variable** — formula `base + sqm_rate * size_sqm + rooms_rate * num_rooms`.
- **One-off** — single charge to a building/apartment.

Each schedule selects a `bill_payer_rule` (default: `current_bill_payer`). At cycle generation time, the BillingModule calls `resolveBillPayer()` (§3.6.4) per apartment to populate `charges.billed_to_person_id`.

API:
```
POST /v1/charge-schedules
{
  "building_id": "...",
  "name": "ועד בית 2026",
  "cadence": "monthly",
  "day_of_month": 1,
  "type": "per_apartment_fixed",
  "amount": 350,
  "currency": "ILS",
  "installments_allowed": 6,
  "bill_payer_rule": "current_bill_payer",
  "start_date": "2026-06-01"
}
```

### 11.2 Billing cycles

- Cron at 02:00 Asia/Jerusalem daily; BullMQ job `billing.run-due-schedules`.
- For each due schedule, iterate apartments, resolve bill payer, create `charges` rows.
- **Dry run preview**: `POST /v1/charge-schedules/:id/dry-run?date=2026-06-01` returns the rows that would be created (including the resolved bill_payer name per apartment) without writing.
- **Unresolved bill payer** → `charge.status='unbilled_no_payer'`; surfaced in admin "Unbilled queue" with mgmt action required.

### 11.3 Tranzila integration

- Use Tranzila iframe ("Iframe Hosted Fields") on web/mobile to stay PCI SAQ-A.
- Tokenization endpoint creates `tranzila_token` saved on `payment_methods.owner_person_id`.
- Recurring charges:
  - `POST https://secure5.tranzila.com/cgi-bin/tranzila71u.cgi` with `TranzilaTK` token, `sum`, `currency=1` (ILS), `tranmode=AK` (deferred capture J5 then J4 capture nightly), or `tranmode=V` (immediate capture).
  - 3DS2 enforced on first transaction per token.
- Refunds: `tranmode=R` with original `index`.
- Webhook (Tranzila Notify URL): `POST /v1/webhooks/tranzila` with HMAC signature verification (`X-Tranzila-Signature`); idempotency via `tranzila_txn_id`.
- Each `Payment` records `paid_by_person_id` (the cardholder/payer) which may differ from `charges.billed_to_person_id` (e.g., owner steps in to pay an overdue renter charge — surfaced in UI as "Paid on behalf of <renter name>").

### 11.4 Retries & dunning

Configurable per tenant. Default policy:
- T+0 fail → retry in 24h with same token.
- T+3 → email reminder to `billed_to_person_id`.
- T+7 → SMS + WhatsApp reminder to `billed_to_person_id`.
- T+14 → push + WhatsApp; **also notify apartment owner** if `billed_to_person_id != owner` (renter is late, owner needs to know per Israeli rental law).
- T+21 → final notice (template, certified-style); create internal task for mgmt.
- T+30 → flag charge `legal_review`; force-notify both bill_payer and owner.

### 11.5 Payment links

`POST /v1/charges/:id/payment-link` → short URL `https://pay.<domain>/<slug>` with signed JWT; opens hosted Tranzila page; SMS/WhatsApp/email distribution included.

The hosted page identifies the payer as `billed_to_person_id` but allows any logged-in person on the same apartment (e.g., owner paying for renter) to complete payment; the resulting `Payment.paid_by_person_id` records the actual cardholder.

### 11.6 Offline payments

Cash / check / wire recorded by mgmt user with proof image. Auto-matches to `charges` by `(building_id, apartment_id, amount, ±7 days)`; unmatched go to a reconciliation inbox.

### 11.7 Installments

1–12 (Israeli market norm). Recorded on `payments.installments`. Receipts show installment plan.

### 11.8 Receipts (חשבונית מס/קבלה)

Hebrew, A4, contains: tenant legal name, VAT id (`עוסק מורשה`), invoice number (sequential per tenant), date, payer details (paid_by_person — actual cardholder for legal accuracy), description (in Hebrew), VAT breakdown (17%), total. Generated via `@react-pdf/renderer`. Conform to Israeli Tax Authority format. When `paid_by_person != billed_to_person` (e.g., owner paid for renter), receipt shows both names: "Paid by X on behalf of Y".

### 11.9 Accounting export

- CSV: `apps/api/src/modules/billing/exports/` with column maps per system.
- Integration hooks (write-only adapters): Hashavshevet, Rivhit, Priority, Wizcount — implemented as `accounting.adapter.<name>.ts` behind an `AccountingAdapter` interface.

### Acceptance criteria

- A monthly charge of ₪350 generated on the 1st is paid by a resident with a saved card in <30 seconds end-to-end.
- A Tranzila webhook replayed twice does not double-credit the charge.
- A Hebrew receipt validates against an accountant's eyeball test (sample with real CPA review).
- A rental scenario: owner pays an overdue renter charge → receipt correctly attributes both parties; report aggregates correctly.

---

## 12. Vendor & Vendor Payouts

### 12.1 Vendor directory

CRUD; ratings; tags by service.

### 12.2 Invoices

Upload PDF/image; OCR via Claude vision (`claude-sonnet-4-6`) to pre-fill vendor, amount, VAT, date; approval workflow (single or two-step per tenant settings).

### 12.3 Payouts

Two paths:
- **Tranzila vendor payout** (where supported).
- **Masav file** — generate an Israeli inter-bank `MASAV` formatted file (fixed-width, IL spec) for upload to the building's bank portal. Schema details in `packages/shared/src/masav/`.

### 12.4 Year-end reports

Per-vendor totals, exportable PDF + CSV (Israeli 1099-like).

### Acceptance criteria

- Generated Masav file passes Bank Hapoalim test validator.
- OCR pre-fill accuracy on 20-invoice sample ≥ 90% on amount and date.

---

## 13. WhatsApp Customer Service

### 13.1 Setup

- Meta Business Manager → WhatsApp Business Account → app + system user.
- Phone number per tenant (we provision; or BYO via Embedded Signup).
- Templates pre-approved per locale (Hebrew first):
  - `charge_reminder_he`
  - `charge_overdue_owner_copy_he` (sent to owner when renter is late)
  - `ticket_update_he`
  - `welcome_he`
  - `otp_he` (transactional)
  - `poll_invite_he`

### 13.2 Inbound webhook

`POST /v1/webhooks/whatsapp` (signature verified via `x-hub-signature-256`). Events: `messages`, `statuses`. Each inbound message:
1. Resolve `tenant_id` from phone-number id mapping.
2. Find/create `Conversation`.
3. Match sender phone to `people.phone_e164` to resolve `person_id` + `apartment_id` (if unique).
4. Append `Message`.
5. Route: if AI bot enabled → push to AI worker queue; else → human inbox.

### 13.3 Outbound

`messages.send` task → BullMQ → Meta Graph API `POST /{phone-number-id}/messages` → store `whatsapp_message_id`.

### 13.4 Routing

State machine per conversation: `bot → bot (loop)` until escalation predicate (low-confidence response, explicit "human" intent, off-topic financial promise) → `pending_human` → mgmt picks up.

### 13.5 Media

Inbound media downloaded within 5 min (Meta TTL), stored to Supabase Storage, attached to `Message`.

### 13.6 Business hours

Per-tenant working hours; outside hours → bot replies "we're closed, will reply at ..." but still queues for human if escalation.

### Acceptance criteria

- A resident texts "מתי גוזרים את הגינה?" from a real WhatsApp client; bot replies in Hebrew within 8 seconds.
- Sending a `charge_reminder_he` template to 100 residents in batch is rate-limited but completes within 5 min.

---

## 14. AI Bot Customer Service

### 14.1 Model

`claude-sonnet-4-6`. Streaming for in-app chat; non-streaming for WhatsApp (one reply per turn).

### 14.2 System prompt design

Located at `packages/ai/prompts/customer-service.he.md`, versioned. Includes: persona ("נציג שירות לקוחות אדיב של חברת {{tenant_name}}"), scope rules, refusal patterns, escalation triggers, formatting rules. The prompt receives context: the person's name, their role(s) per apartment, whether they're bill_payer, and outstanding balance.

### 14.3 Tool use (Claude tool API)

Tools (declared with JSON schema in `packages/ai/tools/`):

- `lookup_balance(person_id, apartment_id?)` → outstanding charges (filtered by role: renter sees only their billed charges; owner sees apartment-wide).
- `lookup_ticket(ticket_id)` → status.
- `create_ticket(person_id, apartment_id, category, description, photos[])`.
- `schedule_callback(person_id, when)` → creates a mgmt task.
- `building_info(building_id, key)` → from FAQ KB.
- `search_kb(query)` → RAG.
- `who_is_my_bill_payer(apartment_id)` → answers "מי משלם את הוועד" by reading current `apartment_assignments`.

### 14.4 RAG

Per-tenant KB: docs uploaded in admin → chunked + embedded → stored in `pgvector` table `kb_chunks`.

### 14.5 Guardrails

- Never quote a discount, never promise legal outcomes.
- Always escalate when: confidence < threshold (heuristic via tool failure / repeated apology), user asks for human, user is upset (sentiment), question outside scope.

### 14.6 Memory

Conversation memory = last N=20 messages + tenant FAQ + person profile snapshot. Stored compressed; cleared on `closed`.

### 14.7 Multi-channel

Same tool layer behind: in-app chat, WhatsApp, web widget.

### 14.8 Per-tenant customization

Tone slider (formal/friendly), additional FAQ, escalation rules editable in the admin "AI bot tuning" screen.

### Acceptance criteria

- Bot correctly identifies and creates a ticket from a freeform Hebrew complaint with photo, attaches photo, replies confirming.
- Bot escalates within 1 turn when user types "תן לי בן אדם".
- Bot correctly answers "כמה אני חייב?" with the balance scoped to the asker's role (renter → only their charges; owner → can ask "כמה חייבת דירה 4ב?" and get the full apartment view).

---

## 15. Bulletin Board

### 15.1 Authoring

Tiptap-based rich editor in admin; images via Supabase Storage; video via Mux (or Supabase) with HLS playback.

### 15.2 Audience targeting

- Whole building.
- Specific apartments (multi-select).
- Group tag (e.g., "ועד פעיל", "בעלי חיות").
- Role filter (owners only / renters only / occupants only).

### 15.3 Distribution

On publish: write `BulletinPost` → fanout to `notifications` (push + WhatsApp for opt-ins + email opt) → live update in resident app via Supabase Realtime.

### 15.4 Engagement

Reactions (👍❤️🙏 emoji set). Comments toggle per tenant. Moderation: report → admin queue.

### Acceptance criteria

- A post pinned with `pinned_until` self-unpins exactly on schedule.
- Audience targeting at 200 apartments fans out within 60s.
- Owner-only audience excludes renters even when they are bill_payer.

---

## 16. Polls & Governance

### 16.1 Poll types

`single` (radio), `multi` (checkbox), `ranked` (drag-to-order).

### 16.2 Eligibility

`per_apartment` (1 vote per apartment — primary occupant or owner per policy), `per_resident`, `owner_only` (only `role=owner` assignments — governance votes), `bill_payer_only` (financial votes).

### 16.3 Anonymity

When `anonymous=true`, store `person_id_hash` (HMAC with per-poll salt) instead of raw id.

### 16.4 Digital form signing

For binding decisions: WebCrypto sign-in-browser → store signature (PNG) + signed canonical JSON of the vote + timestamp + public key fingerprint. Aligns with Israeli `חוק חתימה אלקטרונית` (Electronic Signature Law) for "מתקדמת" tier; "מאובטחת" tier deferred.

### 16.5 Audit trail

Append-only `vote_audit_log` table — every state change with hashes chained (`prev_hash`) for tamper-evidence.

### Acceptance criteria

- A poll with 50 apartments closes on schedule; results computed correctly; signatures verify.
- Anonymous poll: querying by `person_id` returns no votes.
- An `owner_only` poll correctly rejects a renter's vote attempt with a friendly message.

---

## 17. Task Management

### 17.1 Types

- **Planned recurring** — generated from templates (e.g., "ניקוי מים בקיץ — אוגוסט, כל שנה").
- **Reactive** — auto-created from a `ServiceTicket` on triage.

### 17.2 Fields & UX

Priority, SLA, dependencies, checklists, time tracking, cost. Customer-visible flag controls whether the linked ticket sees updates.

### 17.3 Assignment

- **Manual** — drag-drop.
- **Round-robin** — by team.
- **Skills-based** — match `task.category` to `worker.skills_json`.

### 17.4 Views

- **Kanban** — by status.
- **Calendar** — by `scheduled_at`.
- **Map** — by building geo; pins colored by priority.

### Acceptance criteria

- A planned task series correctly generates 12 monthly instances on creation.
- Skills-based assignment proposes only workers whose `skills_json` includes the task category.

---

## 18. Service Tickets

### 18.1 Intake channels

App, WhatsApp, AI bot, walk-in (mgmt enters on behalf), phone log (mgmt enters).

### 18.2 Triage

On creation, call Claude classifier to set `category` (plumbing/electrical/elevator/cleaning/security/other). User can override.

### 18.3 Internal vs resident-visible comments

`messages.visibility` enum: `resident | internal`. Visible to all current `apartment_assignments` for the ticket's apartment per the apartment's `notification_policy`.

### 18.4 Workflow

`new → triaged → assigned → in_progress → pending_parts → resolved → closed`. Transitions logged in `audit_log`.

### 18.5 SLA

Default by category, override per tenant. Breach → escalate to mgmt_admin via push + email + WhatsApp.

### 18.6 Satisfaction

On `closed`, prompt resident for 1–5 star + optional comment.

### Acceptance criteria

- A ticket created via WhatsApp lands in the same inbox as one from the app.
- SLA timer pauses on `pending_parts`.
- When a renter opens a ticket about a leak, the absentee owner is notified per `notification_policy` (legal access notice).

---

## 19. Addon Products Module

### 19.1 Catalog

Mgmt-managed; per-product availability list of buildings. Example SKUs: locksmith call-out, AC summer service, smart lock installation, insurance offer (referral), cleaning supplies bundle.

### 19.2 Resident purchase flow

Resident (any role) taps "Add to cart" → checkout → Tranzila → on success: `addon_orders` row → notification to mgmt → fulfillment status workflow. `ordered_by_person_id` records the actual buyer.

### 19.3 Commission

`commission_pct` on product; revenue split tracked in reports; payouts to mgmt happen automatically as part of the resident's Tranzila settlement.

### Acceptance criteria

- Purchase, refund, fulfillment status update all flow without errors.
- A product disabled for Building X is invisible to a resident of Building X.

---

## 20. Access Control (Parking Gate, etc.)

### 20.1 Integration approach

`AccessProvider` interface with implementations:
- `HttpWebhookProvider` (POST to a gate controller URL with HMAC).
- `MqttProvider` (publish to topic).
- `SesameStyleProvider` (REST + bearer).
- `CustomProvider` (extensible).

### 20.2 Features

- **One-tap open from the resident app** — large prominent "Open gate" button on Home for any user with `is_occupant=true` on an active assignment for the building. Haptic feedback on tap; loading state; success/fail toast; relay status fetched live (open/closed/unknown).
- Per-user gate access list (some occupants may have access to pedestrian but not parking gate, etc.).
- Time-based access (visitor window).
- Guest codes (`GuestCode` table) — 6-digit codes, single/multi-use, expiry; sharable via WhatsApp deep link `wa.me/?text=...code...`.
- Audit log on every open (`AccessEvent.person_id`, `source`, `gate_id`, latency ms).
- Push notification to a configurable subset of mgmt users on suspicious patterns (e.g., same code used 5 times in 1 hour).

### 20.3 Resident app flow (parking gate)

1. Resident opens app → Home → "פתח שער חניה" button (large, prominent).
2. Tap → optimistic UI ("opening...") → API call `POST /v1/gates/:id/open` (debounced, idempotency key per second).
3. API verifies: user has active occupant assignment for building, gate is `active`, rate limit OK.
4. API dispatches to provider adapter; provider response within 3s.
5. Success → success animation; record `AccessEvent`. Failure → user-friendly Hebrew error + escalate to mgmt if recurring.

### Acceptance criteria

- Latency from tap-to-gate-open under 3 seconds on 4G.
- Revoking a guest code immediately invalidates it.
- Absentee owners cannot open gates; only occupants can.
- The "open gate" button is reachable from Home in ≤1 tap.

---

## 21. Notifications Engine

Path: `apps/api/src/modules/notifications`.

### 21.1 Channels

- **Push**: Expo Push Service.
- **Email**: Resend (Israeli IPs configured).
- **SMS**: Inforu (primary), 019 (fallback). Hebrew-safe (Unicode SMS).
- **WhatsApp**: WhatsApp module.

### 21.2 Templates

`packages/shared/src/templates/` — Hebrew/English, named like `charge_reminder.he.md`. Variables interpolated; preview API; per-tenant overrides.

### 21.3 Preferences

Per-person channel preferences stored on `people.notification_prefs jsonb`. Defaults set on signup.

### 21.4 Fanout (incorporates §3.6.6 notification_policy)

For each apartment-scoped event, the engine reads the apartment's `notification_policy`, resolves to a set of `person_id`s, then per person dispatches per channel preferences. Deduplication by `(person_id, event_key, dedupe_window)`.

### 21.5 Rate limits & DND

- Per person: max 5 non-critical notifications/day.
- Do-not-disturb (default 21:00–07:00 Asia/Jerusalem); critical (security/payment failure) bypasses.

### 21.6 Architecture

`Notification` row written → BullMQ job per channel → provider call → status update via webhook (where available).

### Acceptance criteria

- Sending the same notification twice for the same `dedupe_key` only delivers once.
- DND respected; verified with timezone-aware tests.
- Owner receives copy-notice for a renter-owed overdue charge per default policy.

---

## 22. Reports & Analytics

### 22.1 Operational

- Open tickets by building/age.
- SLA breaches by category.
- Worker productivity (tasks completed, avg cycle time).
- Recurring issues (clustered by category + building).

### 22.2 Financial

- Cash flow (in / out).
- Collection rate (paid / billed).
- AR aging buckets (0–30 / 31–60 / 61–90 / 90+).
- Per-person AR (e.g., absentee owner of 8 units across buildings — total balance view).
- Vendor spend by category.
- Per-apartment P&L (including rental-period attribution: which payer covered which period).

### 22.3 Engagement

- App DAU/MAU, push CTR, WhatsApp engagement, bulletin reach.

### 22.4 Export

CSV (UTF-8 with BOM for Excel-Hebrew), PDF (server-side), XLSX (via `exceljs`).

### Acceptance criteria

- A 12-month financial report renders for a building with 100 apartments in under 5 seconds.
- Per-person AR view aggregates correctly across multiple apartments (multi-unit owner).

---

## 23. Admin Map View

- Mapbox GL JS (or MapLibre).
- Pins = buildings; color = composite health (green / amber / red) based on `(collection_rate, open_ticket_count, sla_breaches)`.
- Clustering at zoom-out; aggregations per city.
- Click pin → drawer with KPIs and "open building" link.

### Acceptance criteria

- 500 pins render at 60fps on a mid-range laptop.
- Health colour matches the building detail KPIs (no divergence).

---

## 24. Audit Log & Compliance

### 24.1 Audit log

- Append-only `audit_log` table.
- Every state change writes via a service-layer interceptor.
- `before_json` / `after_json` diffs (including assignment changes — owner sold, renter moved out, bill_payer flipped).
- Hash chain (`prev_hash` column) for tamper-evidence; rolled into daily anchor stored in S3-equivalent.

### 24.2 Compliance

- Israeli `חוק הגנת הפרטיות (תשמ"א-1981)` + GDPR (we serve EU residents potentially).
- Data residency: `eu-west-1` (Supabase). DPA template at `/legal/dpa`.
- Right to erasure: `DELETE /v1/me/erase` triggers a job that anonymizes a Person's PII (keeps financial records under Israeli accounting retention law — 7 years; charges retain `billed_to_person_id` as a hash for audit).
- Data export: `GET /v1/me/export` returns JSON + ZIP of files.

### Acceptance criteria

- Erasure flow finishes in <24h and reports completion to the resident.
- Audit log gaps detected by daily integrity job → alert.

---

## 25. Security

### 25.1 Threat model summary

OWASP Top 10 + multi-tenant data leakage + payment fraud + SMS pumping (throttle) + AI prompt injection (sanitize tool inputs) + cross-role data leakage (renter sees owner's PII or vice versa).

### 25.2 Secrets

Supabase Vault for DB-side; Doppler for app config (`apps/api`, `apps/admin`, etc.). No secrets in repo; `.env.example` checked in.

### 25.3 Encryption

- At rest: Supabase default (AES-256).
- In transit: TLS 1.2+ enforced.
- App-level: `id_number_encrypted` and any other sensitive field encrypted with `pgcrypto` using a key from Vault.

### 25.4 PII tagging

`files.pii_tag` and column-level annotations; logs scrub PII via Pino redactors.

### 25.5 PCI scope

Tranzila iframe (Hosted Fields) keeps us at **SAQ-A**. We never see PAN/CVV. Annual self-assessment template included.

### 25.6 Rate limiting & WAF

- API: `@nestjs/throttler` + Redis store.
- WAF: Cloudflare in front of all public domains; OWASP managed rules + IL geo allow.

### 25.7 SOC2 readiness checklist

Access reviews quarterly, change management via PR + CODEOWNERS, vulnerability scanning (Snyk weekly), incident response runbook (`docs/runbooks/incident.md`), key rotation 90d.

### Acceptance criteria

- `npm audit --production` clean (or documented).
- Pen test (3rd party) passed before GA.
- Cross-role leakage test in CI: renter cannot read owner's contact info unless owner opts in.

---

## 26. Performance & Scaling

### 26.1 SLOs

- API p95 latency < 400ms (non-payment endpoints).
- Payment endpoints p95 < 2s.
- Web LCP < 2s in Israel.
- Mobile cold start < 2.5s on a 2-year-old Android.

### 26.2 Caching

- Redis for hot reads (`tenant.settings`, `building.summary`, `apartment.current_bill_payer`).
- CDN: Vercel Edge for marketing + admin static; Cloudflare for API static assets.

### 26.3 DB indexes

See §4.4. Plus `pgvector` IVFFlat for KB chunks.

### 26.4 Background jobs

BullMQ on Redis. Queues: `billing`, `notifications.push`, `notifications.email`, `notifications.sms`, `notifications.whatsapp`, `ai.completions`, `files.scan`, `reports.export`. Concurrency tuned per queue.

### Acceptance criteria

- k6 load test: 200 RPS sustained for 10 min, error rate <0.5%.

---

## 27. Observability

- **Logging**: Pino → stdout → Vector → Loki. Per-request correlation id (`X-Request-Id`).
- **Errors**: Sentry (`@sentry/nextjs`, `@sentry/node`, `@sentry/react-native`).
- **Metrics**: Prometheus client → Grafana Cloud dashboards.
- **Tracing**: OpenTelemetry → Grafana Tempo.
- **Uptime**: Better Stack pings every 1 min on `/healthz`.
- **Alerting**: PagerDuty rotation; alerts: p95 latency, 5xx rate, queue backlog, failed payments rate, AI quota.

### Acceptance criteria

- A simulated DB outage pages on-call within 90s.

---

## 28. Internationalization & Localization

- Primary: `he-IL` (RTL). Secondary: `en-US`, `ru-RU`, `ar-IL` (resident-only).
- Library: `next-intl` (web), `i18next` + `react-i18next` (mobile).
- Money: ILS `₪` formatted `Intl.NumberFormat('he-IL', { style: 'currency', currency: 'ILS' })`.
- Dates: `Asia/Jerusalem`, format `dd/MM/yyyy`.
- Phones: `libphonenumber-js` E.164, default `IL`.
- Addresses: free-text `address_line` + structured `city/postal_code`; geocoding via Google Geocoding API.

### Acceptance criteria

- All UI in `he` and `en` complete with no missing keys (CI lint).

---

## 29. Repository & Project Structure

Monorepo: **Turborepo** + **pnpm workspaces**.

```
/
├─ apps/
│  ├─ marketing/         # Next.js 14 marketing site
│  ├─ admin/             # Next.js 14 admin web
│  ├─ mobile-resident/   # Expo RN resident app
│  ├─ mobile-maintenance/# Expo RN maintenance app
│  ├─ desktop/           # Electron wrapper of admin
│  └─ api/               # NestJS API + workers
├─ packages/
│  ├─ shared/            # Pure TS: types, schemas (Zod), constants, templates
│  ├─ ui/                # shadcn-based component library, Tailwind preset
│  ├─ types/             # Generated types from OpenAPI / Prisma
│  ├─ db/                # Prisma schema + Supabase migrations
│  ├─ ai/                # Prompts, tools, classifiers, RAG helpers
│  └─ config/            # eslint, tsconfig, tailwind, jest, vitest presets
├─ infra/                # Terraform / Supabase config / GH Actions reusable
├─ docs/                 # Architecture decision records, runbooks
├─ turbo.json
├─ pnpm-workspace.yaml
└─ package.json
```

API surface contract: **tRPC** between admin web and API for internal speed; **REST/OpenAPI** for mobile clients (cleaner versioning); **Webhook** routes are REST only. Types codegen via `openapi-typescript`.

### Acceptance criteria

- `pnpm install && pnpm build` succeeds from clean clone.
- `pnpm turbo run typecheck` is green.

---

## 30. DevOps & CI/CD

### 30.1 GitHub Actions

Workflows in `.github/workflows/`:
- `ci.yml` — lint, typecheck, unit + integration tests, build all apps, Playwright on `apps/admin`.
- `deploy-marketing.yml` — Vercel.
- `deploy-admin.yml` — Vercel.
- `deploy-api.yml` — Fly.io (or Railway), Docker build & push.
- `migrate-db.yml` — supabase CLI applies migrations.
- `mobile-eas.yml` — EAS Build (preview on PR, production on tag).
- `desktop-release.yml` — electron-builder → GitHub Releases (mac+win).

### 30.2 Environments

- `dev` (per-developer Supabase project).
- `staging` (shared; preview deploys point here).
- `prod`.

### 30.3 DB migrations

`supabase migration new <name>` → SQL files in `packages/db/supabase/migrations`. `supabase db push` in CI.

### 30.4 Env management

Doppler projects per env; CI pulls via `doppler run`. `.env.example` lists keys without values.

### 30.5 Preview deploys

Every PR: Vercel previews for `marketing` + `admin`; ephemeral API deploy on Fly.io with PR-suffixed app name + ephemeral Supabase branch.

### Acceptance criteria

- A PR opens, all checks pass, preview URLs are commented within 8 min.

---

## 31. Testing Strategy

- **Unit**: Vitest. ≥80% coverage on domain logic in `apps/api` and `packages/shared`.
- **Integration (API)**: Supertest against a real Postgres (Testcontainers Supabase image).
- **E2E (web)**: Playwright; runs against staging deploy + a fresh seed.
- **E2E (mobile)**: Detox on EAS Build artifacts.
- **Contract**: schemas codegen + zod parse on incoming webhook payloads.
- **Load**: k6 scripts in `infra/k6/`.
- **Seed data**: `pnpm db:seed` (idempotent), produces the demo tenant described in §4 with all four rental scenarios (owner-occupant / renter-pays / owner-pays-for-renter / split).

### Test plan per module

Each module ships with: unit (services), integration (controllers), e2e for the top user flow, plus a "negative test" verifying RLS isolation. Billing has explicit scenario tests for each of A/B/C/D.

### Acceptance criteria

- CI runs all suites; total <15 min wall-clock.

---

## 32. Onboarding Flows

### 32.1 Management company self-serve

1. Visitor on marketing → `/signup`.
2. Form: email, password, company name, phone.
3. Supabase signUp → `handle_new_auth_user` creates `tenants` row in `trial`.
4. Confirm email.
5. Wizard: branding (logo upload), team invites, first building.
6. After first building → flyer generator suggested.

### 32.2 Building creation + flyer

1. Mgmt user → "Add building" → form (name, address, geo auto, # apartments).
2. Bulk apartment creation (CSV import or # range generator).
3. Mgmt assigns known owners per apartment (bulk import of owners with phone numbers).
4. "Generate flyer" → returns 4 variants.
5. Distribute (download / send to print partner / share to building WhatsApp group).

### 32.3 Resident onboarding (3 paths)

**Path A — Owner self-claims via QR (owner-occupant or absentee):**
1. Owner scans QR → universal link → resident app opens at claim screen.
2. Phone OTP (Supabase phone auth).
3. Unit number + full name + role=owner.
4. If `apartments + people` already matched by phone → auto-approve as primary owner.
5. Owner is asked: "Do you live here?" → sets `is_occupant`. "Do you pay the va'ad?" → sets `is_bill_payer` if no rental contract exists yet.

**Path B — Renter scans QR while owner already onboarded:**
1. Renter scans QR → claim screen.
2. Phone OTP → unit number + name + role=renter.
3. System recognizes a `RentalContract` may be required → asks: "האם הבעלים יודע שאתם גרים כאן?".
4. If "yes" + owner phone provided → assignment created `pending_owner_confirm`; owner gets push to confirm.
5. If "no" → assignment created `pending_mgmt_approval`; mgmt sees in admin and either creates a `RentalContract` (validates rental scenario) or rejects.
6. On approval: renter assignment activated; if `RentalContract.vaad_responsibility=renter_pays` → `is_bill_payer=true` automatically; charges going forward route to renter.

**Path C — Mgmt enters rental contract first, then invites renter:**
1. Mgmt opens apartment → "Start rental contract" wizard.
2. Selects owner (existing), enters renter phone + name, dates, va'ad responsibility.
3. System sends invite SMS to renter with deep link.
4. Renter installs app, OTP, lands on auto-prefilled claim screen → confirms.
5. Assignments and bill_payer flags set per contract.

### 32.4 Maintenance worker

1. Mgmt invites via "Add worker" → SMS magic link via Supabase OTP.
2. Worker installs maintenance app → enters phone → OTP → password set.
3. Skills + availability captured.
4. First task ready.

### Acceptance criteria

- Mgmt company can go from signup to "resident pays first ₪350" in under 30 minutes.
- All three resident onboarding paths (A/B/C) work and route the next charge to the correct person.

---

## 33. Pricing Model (for the SaaS itself)

### 33.1 Tiers

| Tier | Buildings | Apartments | Monthly | Notes |
|---|---|---|---|---|
| Trial | up to 1 | up to 20 | Free 30 days | All features |
| Starter | up to 3 | up to 100 | ₪399/mo | Standard |
| Pro | up to 15 | up to 600 | ₪1,290/mo | + AI bot, + accounting export |
| Enterprise | Unlimited | Unlimited | Custom | + SLA, + SSO, + dedicated CSM |

### 33.2 Transaction fees

- Card payments: 0.9% + ₪1.20 (markup over Tranzila); offline payments: free.
- Addon products commission: configurable (default 8%); shared per tenant agreement.

### 33.3 Billing of the SaaS itself

Stripe (or Tranzila with our own merchant) for SaaS subscription. Tax handling for IL VAT 17%.

### Acceptance criteria

- Plan limits enforced at create-time (e.g., adding a 4th building on Starter shows upgrade prompt).

---

## 34. Roadmap & Milestones

Even as an all-at-once spec, Claude Code builds in this order (each milestone shippable internally):

### M0 — Infra (week 1)
Repo, CI, Supabase project, Doppler, baseline NestJS + Next.js skeletons.
**Acceptance**: hello-world API responding at `/healthz`; marketing landing loads.

### M1 — Auth + Core Domain (weeks 2–3)
Tenants, Buildings, Apartments, People, ApartmentAssignments, RentalContracts, ManagementUsers, MaintenanceWorkers; RLS; invitations; admin scaffolding.
**Acceptance**: full CRUD wired with RLS proven; the 4 rental scenarios are seedable and assignment timeline displays correctly.

### M2 — Billing + Invoicing + Checks (weeks 4–6)
ChargeSchedule, Charge, Payment, Tranzila integration, bill-payer resolution, dunning, **tax-compliant Invoices & Receipts (§37) with ITA sandbox clearance**, accounting export, **Check management incl. bounced-check workflow (§38)**.
**Acceptance**: real ₪1 test transaction end-to-end with refund; renter scenario charges route to renter, owner gets copy on overdue; tax invoice issued with gap-free serial + ITA allocation number; bounced check fully reverses and reroutes.

### M3 — Tickets + Tasks + Documents (weeks 7–8)
Ticket intake, triage, tasks board, worker scheduling, **Document Vault per building (§39)** incl. AI summary + expiry reminders.
**Acceptance**: ticket → task → completion with photos; insurance doc upload triggers expiry reminder 30 days out.

### M4 — Mobile apps + Gate access (weeks 9–10)
Resident + maintenance Expo apps; push; offline queue; QR claim; multi-apartment switcher; **one-tap parking gate open from Home (§20.3)**.
**Acceptance**: TestFlight + Internal Testing builds installed and used; gate opens in <3s on 4G.

### M5 — WhatsApp + AI (weeks 11–12)
WhatsApp Cloud API, AI bot with tools, escalation, RAG.
**Acceptance**: bot handles 80% of seeded queries in Hebrew including role-aware balance lookups.

### M6 — Polish + Marketing GA (week 13)
Marketing site, pricing, blog, ROI calc; reports; map view; addon products.
**Acceptance**: external beta with 3 paying mgmt companies.

---

## 35. Glossary (Hebrew ↔ English)

| Hebrew | Translit. | English |
|---|---|---|
| חברת ניהול ואחזקה | chevrat nihul ve-achzaka | Building management company |
| ועד בית | va'ad bayit | Building committee (HOA) |
| דייר | dayar | Resident (generic) |
| בעל דירה | ba'al dirah | Apartment owner |
| שוכר | sokher | Renter (tenant of the apartment) |
| בעלים נעדר | be'alim ne'edar | Absentee owner |
| חוזה שכירות | chozeh schirut | Rental contract |
| משלם הוועד | meshalem ha-va'ad | Bill payer (va'ad fees) |
| איש אחזקה | ish achzaka | Maintenance worker |
| תקלה / פנייה | takala / pniya | Issue / service ticket |
| חיוב | chiyuv | Charge |
| גבייה | gviya | Collection |
| הוראת קבע | hora'at keva | Standing order (direct debit) |
| מס"ב / מסב | masav | Inter-bank clearing file |
| חשבונית מס | cheshbonit mas | VAT invoice |
| קבלה | kabala | Receipt |
| עוסק מורשה | osek murshe | Authorized dealer (VAT id) |
| ח.פ. | ch.p. | Company number |
| לוח מודעות | luach moda'ot | Bulletin board |
| סקר | seker | Poll |
| חתימה אלקטרונית | chatima electronit | Electronic signature |
| שער חניה | sha'ar chanaya | Parking gate |
| חשבונית מס | cheshbonit mas | Tax invoice |
| חשבונית מס/קבלה | cheshbonit mas/kabala | Tax invoice/receipt (combined) |
| חשבונית זיכוי | cheshbonit zikuy | Credit note |
| מספר הקצאה | mispar haktsa'a | ITA allocation number (e-invoicing) |
| צ'ק | check | Check |
| צ'ק חוזר | check chozer | Bounced check |
| צ'ק דחוי | check dachui | Post-dated check |
| הפקדת צ'קים | hafkadat checkim | Check deposit (batch) |
| תקנון בית | takanon bayit | Building bylaws |
| פרוטוקול אסיפה | protocol asefa | Meeting protocol (AGM/committee) |

---

## 36. Open Questions / Decisions Deferred

Claude Code should ask the operator before assuming:

1. **Tranzila merchant accounts** — one master vs. per-tenant sub-merchant routing?
2. **Bllink-style line of credit** — do we own the credit risk, or partner with an Israeli lender? Default: partner only.
3. **WhatsApp numbers** — pool we own vs Embedded Signup? Default: Embedded Signup for new tenants, pool for trials.
4. **Resident KYC** — depth? Default: phone OTP + name; deeper for line-of-credit.
5. **Mobile push for iOS** — APNs key vs p12? Default: APNs key via Expo.
6. **Accounting integration launch partner** — Default: Rivhit first.
7. **Hebrew TTS / STT** — Whisper API for STT, no TTS in v1.
8. **Hosting region** for API — Fly.io `cdg` (Paris). Confirm latency to Tranzila is acceptable.
9. **Receipts numbering** — per tenant (default) vs per building?
10. **Polls binding-vote tier** — `חתימה מאובטחת` (hardware token) in v1? Default: no.
11. **Owner-renter PII exposure** — by default, does the renter see the owner's phone, or only their name? Default: name only; owner can opt in to share contact.
12. **Owner approval on renter self-claim** — required (Path B), or mgmt-only? Default: owner confirms if known; else mgmt arbitrates.
13. **Multi-tenant person dedup** — if a person rents in two different mgmt companies' buildings, are they two `Person` rows or one with cross-tenant link? Default: scoped per tenant (two rows); no cross-tenant identity in v1.

---

## Verification (end-to-end validation)

Before declaring done, run the following:

### Local dev verification

1. `pnpm install` from clean clone.
2. `supabase start` brings up local stack.
3. `pnpm db:migrate && pnpm db:seed`.
4. `pnpm turbo run dev` boots all apps:
   - Marketing on `:3000`.
   - Admin on `:3001`.
   - API on `:4000`.
   - Mobile resident on Expo (QR to phone).
   - Mobile maintenance on Expo.
5. Visit `http://localhost:3000` → sees Hebrew RTL hero.
6. Sign up → tenant created → admin dashboard loads with seed data.
7. Create building → import 10 apartments + 10 owners → generate flyer → 4 variants returned with Hebrew rendered.
8. Scan QR on phone (universal link to local tunnel) → claim as owner → claim flow completes.
9. In admin, create a `RentalContract` for one apartment (owner X → renter Y, va'ad=renter_pays).
10. Renter installs app, OTPs in, sees their charges due.
11. Renter pays via Tranzila **sandbox** card → receipt PDF downloads in Hebrew with payer = renter, billed = renter.
12. Switch to a "owner_pays" scenario: owner pays an overdue renter charge → receipt shows "Paid by owner on behalf of renter".
13. Resident opens a ticket with photo → mgmt triages → assigns worker → worker app shows it → worker marks done → renter + owner both receive push (per policy).
14. Resident sends WhatsApp message to tenant number → bot replies in Hebrew, correctly identifies role (renter) and answers balance scoped accordingly → asks for human → escalates → mgmt replies.
15. Mgmt publishes bulletin to all → push received on resident phone (correct apartment context).
16. Mgmt creates owner-only poll → renter cannot vote (UI hides it); owner votes → result correct.
17. Open `/reports/collection` → shows correct collection rate including the ₪350; per-person AR shows owner X has 0 balance, renter Y has paid.
18. Verify auto-issued tax receipt (`חשבונית מס/קבלה`) PDF has sequential number, ITA allocation number (sandbox), correct Hebrew formatting, both payer + billed party shown.
19. Upload a building insurance policy PDF with `expires_at` set 25 days ahead → confirm task is auto-created and reminder fires.
20. Resident on Home → tap "פתח שער חניה" → gate opens within 3s; AccessEvent recorded.
21. Mgmt records a post-dated check from a renter → marks deposited → marks bounced → original Charge reverts to overdue, recharge-fee Charge appears, renter + owner notified, replacement check linked and resolves the bounce.

### Automated verification

- `pnpm turbo run test` — all unit + integration green.
- `pnpm turbo run e2e` — Playwright + Detox green.
- `pnpm turbo run lint && pnpm turbo run typecheck` — clean.
- `pnpm db:rls-check` — runs negative cross-tenant + cross-role tests; all must fail to access.
- k6 `infra/k6/smoke.js` — 50 RPS for 60s, 0 errors.

### Manual smoke checklist (pre-GA)

- [ ] Hebrew renders correctly on PDF, share images, app screens, push notifications.
- [ ] RTL layouts have no clipped buttons or wrong-side icons.
- [ ] iOS + Android both pass.
- [ ] Tranzila refund works end-to-end.
- [ ] WhatsApp template messages send in production sandbox.
- [ ] Sentry captures a forced error from each app.
- [ ] Backups: Supabase PITR confirmed; restore test done.
- [ ] DPA + Privacy + Terms pages published.
- [ ] On-call rotation set, PagerDuty alerts firing on a forced 500.
- [ ] All 4 rental scenarios (A/B/C/D) verified with real money on Tranzila sandbox.

When all items above pass, the platform is ready for GA.

---

## 37. Invoices & Receipts (Tax-Compliant Israeli Invoicing)

This expands §11.8 into a first-class, tax-compliant invoicing subsystem. Israeli tax law (Israel Tax Authority — `רשות המסים`) requires:

- Sequential, gap-free invoice numbering per `עוסק מורשה` (per tenant).
- Specific document types: `חשבונית מס` (tax invoice), `קבלה` (receipt), `חשבונית מס/קבלה` (combined), `חשבונית זיכוי` (credit note).
- VAT 17% (rate updatable in config; tracked as `vat_rate_pct`).
- As of 2024–2026 e-invoicing reform: invoices over a configurable threshold (currently ₪25,000 → ₪10,000 phased) require **digital clearance** with the ITA — an `allocation_number` (`מספר הקצאה`) must be obtained from the ITA system before issuance.

### 37.1 Entities

```
Invoice
  id, tenant_id
  type            enum (tax_invoice | receipt | tax_invoice_receipt | credit_note)
  series_id       uuid                 -- which numbering series
  serial_number   bigint               -- gap-free per series
  status          enum (draft | issued | sent | cancelled | replaced)
  issued_at       timestamptz
  issued_by_user  uuid
  customer_person_id uuid              -- billed party
  customer_name_snapshot text          -- captured at issuance (immutable)
  customer_address_snapshot text
  customer_vat_id_snapshot text nullable
  description     text
  currency        text default 'ILS'
  subtotal        numeric(12,2)
  vat_rate_pct    numeric(5,2)
  vat_amount      numeric(12,2)
  total           numeric(12,2)
  related_charge_ids uuid[]            -- charges this invoice covers
  related_payment_ids uuid[]           -- payments this receipt acknowledges
  credit_note_for_invoice_id uuid nullable -- when type=credit_note
  pdf_file_id     uuid                 -- generated PDF stored in Storage
  ita_allocation_number text nullable  -- when e-invoicing applies
  ita_clearance_status enum (not_required | requested | approved | rejected) nullable
  ita_clearance_payload jsonb nullable
  delivered_channels jsonb              -- {email: sent_at, whatsapp: sent_at, ...}
  hash            text                  -- content hash for tamper detection

InvoiceSeries
  id, tenant_id, name, prefix, next_serial bigint
  document_type enum                   -- typically one per (tenant, type)
```

### 37.2 Numbering rules

- One `InvoiceSeries` row per (tenant, document type) by default; tenants on `enterprise` may have per-building series.
- `next_serial` advances atomically inside a Postgres transaction with `select ... for update`.
- Issuance is the only action that consumes a number; drafts do not.
- Cancellation does NOT free the number; instead a `credit_note` is issued to reverse.

### 37.3 Issuance flow

1. **Auto-issue** on successful payment: BillingModule emits `payment.captured` → InvoicingModule creates a `tax_invoice_receipt` for that payment, attaches related `Charge`(s), generates PDF, delivers via configured channels.
2. **Manual issue**: mgmt user in admin → "Issue invoice" → wizard (type, customer, lines, VAT) → preview → issue.
3. **ITA clearance** (when threshold met): before persisting, call `ItaClearanceAdapter.request(...)` → receive `allocation_number` → embed in PDF + DB row; if rejected, present error to mgmt and abort.
4. **PDF generation**: `@react-pdf/renderer` server-side; Hebrew fonts embedded; QR code with invoice URL on each page; ITA `allocation_number` printed prominently; tenant branding (logo, colors).
5. **Delivery**: email (Resend) + WhatsApp template `invoice_issued_he` with PDF link + in-app inbox.

### 37.4 Credit notes (`חשבונית זיכוי`)

- Cannot edit issued invoice; must issue a `credit_note` linked via `credit_note_for_invoice_id`.
- UI: from any issued invoice → "Issue credit note" → choose full/partial reversal → confirm → new sequential `credit_note` PDF generated; original invoice marked `replaced`.
- Refund payments are recorded against the credit note for reconciliation.

### 37.5 Bulk operations

- **Mass-issue receipts** at end of month for all paid charges in the period (idempotent).
- **CSV export** of issued invoices for accountant.
- **Period close**: once a period is locked by mgmt, no new invoices can be back-dated into it (auditable).

### 37.6 Tax authority integration

`ItaClearanceAdapter` interface; concrete `IsraelTaxAuthorityAdapter` calls the ITA e-invoicing API per their spec (OAuth2 + signed XML payload). Implementation hidden behind feature flag `features.ita_clearance=true` per tenant. Sandbox environment used in dev/staging.

### 37.7 Display & verification

Each PDF has a QR linking to `https://verify.<domain>/i/<invoice_hash>` — a public page showing invoice metadata (no PII beyond customer name + amount + date) so a customer can verify the invoice authenticity without an account.

### Acceptance criteria

- Issuing 1,000 invoices in a single batch produces gap-free serials with no race conditions (verified under concurrent load).
- A canceled-and-credit-noted flow leaves audit trail and reconciles to ₪0 net.
- ITA clearance call is mocked in tests and works against ITA sandbox in staging.
- All PDFs render Hebrew correctly and pass a CPA's eyeball test.

---

## 38. Check Management (Including Bounced Checks)

Israeli HOAs and management companies still receive physical checks; this module digitizes the entire lifecycle and handles bounced-check (`צ'ק חוזר`) workflows that competitors handle poorly.

### 38.1 Entities

```
Check
  id, tenant_id
  building_id, apartment_id
  payer_person_id            -- from People; may be filled later
  bank_code, branch_code, account_number  -- 3 numeric fields per Israeli check
  check_number               -- printed on check
  amount                     numeric(12,2)
  currency                   default 'ILS'
  issue_date                 -- on the check
  presented_date             -- when received
  due_date                   -- post-dated checks (very common in IL)
  scan_file_id               uuid    -- photo/scan of front + back
  status                     enum (received | scheduled | deposited | cleared | bounced | replaced | voided)
  deposit_batch_id           uuid nullable
  related_charge_ids         uuid[]
  notes
  created_at, updated_at

CheckBatch
  id, tenant_id, building_id
  bank_account_iban
  deposit_date
  total_amount
  check_ids                  uuid[]
  status                     enum (draft | deposited | partially_cleared | fully_cleared)
  bank_deposit_slip_file_id  uuid nullable
  bank_reference             text

BouncedCheck
  id, tenant_id
  original_check_id          uuid
  bounce_reason              enum (insufficient_funds | account_closed | stop_payment | signature_mismatch | other)
  bounce_reason_text         text
  bounced_on                 date
  bank_fee_amount            numeric(12,2)        -- our bank's charge for the bounce
  recharge_fee_amount        numeric(12,2)        -- fee we charge the resident (configurable per tenant)
  recovery_status            enum (open | replacement_received | paid_other | legal_handover | written_off)
  replacement_check_id       uuid nullable
  legal_handover_at          timestamptz nullable
  resolution_notes
```

### 38.2 Check intake

Two flows:

**A — Mgmt enters check in admin**:
1. Click "Add check" → form: phone-scan check (camera) → OCR via Claude vision pre-fills bank/branch/account/check#/amount/issue_date.
2. Select payer (autocomplete from People in building); link to one or more open `Charge`s.
3. Save → status `received` (or `scheduled` if post-dated).
4. Generate digital receipt to payer (Hebrew template) with WhatsApp/SMS link.

**B — Resident hands check to maintenance worker on site**:
1. Worker in maintenance app → "Receive check on behalf" → camera scan + payer link.
2. Worker enters geolocation auto-captured.
3. Check appears in admin queue for mgmt to verify and add to a deposit batch.

### 38.3 Deposit batches

- Mgmt selects a set of checks → groups into a `CheckBatch` → generates a bank-format **deposit slip PDF** with totals + check list.
- Status transitions: `draft → deposited (when mgmt confirms deposit at bank) → cleared (one-by-one as bank confirms)`.
- Integration hook: optional bank API (when supported) auto-marks `cleared`; otherwise mgmt marks manually.

### 38.4 Bounced check workflow (CRITICAL)

When mgmt marks a check `bounced` (manually upon receiving bank notice, or auto via bank integration where available):

1. Original `Charge` status reverts to `pending` (or `overdue` if past due).
2. A `BouncedCheck` row is created with bounce reason.
3. **Auto-actions** (configurable per tenant):
   - Create a new `Charge` for the recharge fee (`bank_fee_amount + recharge_fee_amount`).
   - Send WhatsApp + SMS + email to payer in Hebrew (template `check_bounced_he` with reason, fee, replacement instructions).
   - Notify owner if payer is renter (per `notification_policy`).
   - Create a mgmt task: "Follow up on bounced check #<n> from <payer>".
   - Optionally block future check payments from this payer (configurable; default: warn for 6 months, block after 2nd bounce).
4. Replacement intake: when a replacement check or other payment arrives, link via `replacement_check_id` and close the bounce row.
5. After N days unresolved (configurable, default 30), bounce moves to `legal_handover` status; produces a legal-prep packet (PDF: original check scan, bounce notice, communication log, charge ledger) and notifies mgmt admin.

### 38.5 Reporting

- Open bounced checks aging report.
- Bounce rate per building / per payer.
- Total recovered vs. written off.

### 38.6 Admin UI

- **Checks dashboard** — kanban (`received / scheduled / deposited / cleared / bounced`).
- **Calendar view** — checks by `due_date` (helpful for post-dated checks).
- **Batch builder** — drag checks into a new batch, generate deposit slip.
- **Bounced inbox** — every open bounce; one-click "send reminder" / "mark resolved" / "hand to legal".

### 38.7 Resident-facing

When a resident pays by check, they see in their app:
- Check pending: "צ'ק התקבל — בהמתנה לפירעון בבנק" with check details + thumbnail.
- Cleared: paid.
- Bounced: "הצ'ק חזר. סיבה: <reason>. נא תשלום מחודש עד <date>." — with one-tap re-pay link (Tranzila) that includes the recharge fee bundled.

### Acceptance criteria

- A bounced check correctly reverts the original Charge, creates a fee Charge, and notifies both renter and owner per policy.
- The legal handover packet (PDF) bundles all required artifacts (scan, comm log, ledger) in <10 seconds.
- Post-dated checks appear in the "due" view on their `due_date`, not before.
- A replacement check can be linked to multiple original bounces (rare consolidation case).

---

## 39. Document Vault Per Building

Every building accumulates documents: building permits, insurance policies, vendor contracts, AGM minutes, blueprints, regulatory certificates, fire safety inspections, elevator maintenance certificates. We store them all, version-controlled and ACL'd.

### 39.1 Entities

```
Document
  id, tenant_id, building_id
  apartment_id              uuid nullable      -- some docs are per-apartment (e.g., rental contracts)
  title                     text
  category                  enum (insurance | contract | minutes | permit | blueprint
                                | certificate | financial_report | rental_contract
                                | vendor_invoice | meeting_protocol | bylaws | other)
  description               text
  expires_at                date nullable      -- triggers a reminder task
  reminder_lead_days        int default 30
  tags                      text[]
  current_version_id        uuid              -- pointer to latest DocumentVersion
  visibility                enum (mgmt_only | owners | bill_payers | all_occupants | building_public)
  status                    enum (active | archived | superseded)
  created_at, updated_at, deleted_at

DocumentVersion
  id, document_id, tenant_id
  version_number            int             -- starts at 1, monotonic
  file_id                   uuid            -- in Supabase Storage
  uploaded_by_user_id
  upload_notes
  size_bytes
  mime
  sha256
  ocr_text                  text            -- extracted for search
  ai_summary                text            -- Claude-generated one-paragraph summary
  ai_metadata               jsonb           -- Claude-extracted fields (vendor name, expiry, parties)
  created_at

DocumentACL
  id, document_id, tenant_id
  person_id                 uuid nullable   -- specific person override
  role                      text nullable   -- or by role
  permission                enum (view | download | edit)
```

### 39.2 Upload & versioning

- Drag-and-drop upload in admin (folder per building → category → docs).
- New file for an existing `Document` → creates a new `DocumentVersion`; old versions kept (rollback supported).
- On upload:
  - Virus scan (ClamAV or Supabase scanner).
  - OCR (Claude vision for PDFs/images, or tesseract for cheap fallback).
  - AI summary + metadata extraction via Claude (`claude-sonnet-4-6`): "Summarize this document in one paragraph in Hebrew. Extract: vendor name, expiry date, parties, monetary amounts."
  - Search index populated.

### 39.3 Categories — first-class behavior

| Category | Special behavior |
|---|---|
| `insurance` | `expires_at` mandatory; reminder at -30 days. Renewal task auto-created. |
| `contract` (vendor) | Links to `Vendor`; expiry reminders. |
| `minutes` (AGM/committee) | Audience defaults to `owners`; auto-tagged with date. |
| `permit` | Authority + permit number captured by AI; expiry reminder. |
| `blueprint` | Large files; allow ZIP/CAD; preview via static raster. |
| `certificate` (elevator/fire) | Regulatory expiry tracking — never lose this. |
| `rental_contract` | Linked to `RentalContract` row; only visible to landlord + renter + mgmt. |
| `vendor_invoice` | Linked to `VendorInvoice`. |
| `meeting_protocol` | Optional signed PDF for legal AGM minutes. |
| `bylaws` (תקנון בית) | Public to building; pinned. |

### 39.4 Visibility & ACL

- `mgmt_only` — only mgmt users.
- `owners` — all current owners of the building.
- `bill_payers` — current bill_payers.
- `all_occupants` — all current occupants.
- `building_public` — anyone with a valid building assignment.
- Per-document custom ACL via `DocumentACL` overrides.

Enforced via Postgres RLS + service-layer checks.

### 39.5 Search

- Full-text search (Postgres `tsvector`) over `title + description + ocr_text + ai_summary` weighted.
- Optional `pgvector` embedding-based semantic search ("find documents about elevator inspection from 2023").
- Search exposed in admin and in resident app (scoped to docs the user can see).

### 39.6 Resident app integration

Resident → Apartment → "Documents" tab → tiles by category, search bar. Tap a tile → full-screen viewer (PDF.js for PDFs, native viewer for images). Download with watermark `Downloaded by <name> on <date>` (deterrent against leakage).

### 39.7 Expiry reminders

Daily cron job (`documents.scan-expiries`) finds documents with `expires_at - reminder_lead_days <= today` and:
- Creates a mgmt task "Renew <document title>".
- Notifies relevant mgmt users (push + email).
- Surfaces in admin dashboard under "Expiring documents".

### 39.8 Sharing

- "Share with vendor" → generates a one-time-use signed URL (expiry configurable) → can email/WhatsApp out.
- Audit log of every share + every access via signed URL.

### 39.9 Bulk operations

- Bulk import: ZIP upload → auto-categorize via Claude classifier → mgmt approves before commit.
- Bulk export: download all docs for a building as ZIP (for handover to a new mgmt company).

### Acceptance criteria

- An expiring insurance policy generates a reminder task exactly 30 days before expiry.
- A renter cannot see `mgmt_only` documents even via direct API.
- AI summary is generated within 30 seconds of upload for a 5MB PDF.
- Search returns relevant results in <500ms for a building with 500 documents.
- Document version rollback restores both file and metadata.

---

### Critical Files for Implementation

- `/packages/db/supabase/migrations/0001_init.sql` (Tenants, Buildings, Apartments, People)
- `/packages/db/supabase/migrations/0002_assignments.sql` (ApartmentAssignment + RentalContract + constraints)
- `/packages/db/supabase/migrations/0003_billing.sql` (ChargeSchedule, Charge, Payment)
- `/packages/db/supabase/migrations/0004_invoices.sql` (Invoice + Receipt + sequential numbering)
- `/packages/db/supabase/migrations/0005_checks.sql` (Check, CheckBatch, BouncedCheck workflow)
- `/packages/db/supabase/migrations/0006_documents.sql` (Document, DocumentVersion, DocumentACL)
- `/apps/api/src/modules/apartments/assignment.service.ts` (bill-payer resolution logic)
- `/apps/api/src/modules/billing/billing.service.ts` (cycle generator using assignment.service)
- `/apps/api/src/modules/payments/tranzila.adapter.ts`
- `/apps/api/src/modules/invoicing/invoice.service.ts` (Israeli tax-compliant invoice + receipt issuance)
- `/apps/api/src/modules/invoicing/ita-clearance.adapter.ts` (Israel Tax Authority e-invoicing clearance)
- `/apps/api/src/modules/checks/check.service.ts` (book-in, deposit, bounce handling)
- `/apps/api/src/modules/documents/document.service.ts` (vault per building + ACL)
- `/apps/api/src/modules/ai-bot/claude.service.ts`
- `/apps/api/src/modules/access/gate.controller.ts` (one-tap open + audit)
- `/apps/admin/app/(dashboard)/buildings/[id]/apartments/[aptId]/page.tsx` (assignment timeline UI)
- `/apps/admin/app/(dashboard)/buildings/[id]/documents/page.tsx` (per-building document vault)
- `/apps/admin/app/(dashboard)/checks/page.tsx` (check management dashboard)
- `/apps/mobile-resident/src/screens/ClaimScreen.tsx` (role-aware onboarding)
- `/apps/mobile-resident/src/screens/HomeScreen.tsx` (includes one-tap gate open button)
