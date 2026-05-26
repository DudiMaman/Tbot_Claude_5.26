# Progress Tracker

This document is updated continuously as development proceeds. It is the source of truth on what is done, what is stubbed, and what needs human action.

> See [`SPEC.md`](./SPEC.md) for the master spec. Section numbers below refer to it.

## Status legend

- ✅ Done & working
- 🟡 Scaffolded / stubbed (compiles, has placeholders / mock adapters)
- 🔴 Not started
- 👤 Requires human action (account, credentials, manual setup)

## Milestone status

### M0 — Foundation ✅
- ✅ Monorepo skeleton (pnpm 9 + Turborepo 2)
- ✅ Root configs (tsconfig.base, .prettierrc, .gitignore, .env.example)
- ✅ `packages/db` — full Postgres schema (12 migrations, all entities, RLS)
- ✅ `packages/shared` — Zod schemas, i18n, currency, phone, MASAV builder, templates
- ✅ `packages/types` — API contract types
- ✅ `packages/config` — Tailwind preset (Heebo Hebrew + indigo)
- ✅ `packages/ai` — Claude client, prompts, tool registry, classifier
- ✅ GitHub Actions CI workflow

### M1 — Auth + Core Domain ✅
- ✅ DB: tenants/buildings/apartments/people/mgmt_users/workers + RLS
- ✅ DB: apartment_assignments + rental_contracts + sync triggers (§3.6)
- ✅ NestJS bootstrap (main, AppModule, DbModule, HealthController)
- ✅ AuthModule: SupabaseJwtGuard, RlsContextInterceptor, RolesGuard, Public decorator
- ✅ TenantsModule (signup, branding)
- ✅ BuildingsModule (CRUD)
- ✅ ApartmentsModule + AssignmentService.resolveBillPayer (FULL ALGORITHM §3.6.4)
- ✅ PeopleModule (CRUD + QR claim flow with phone matching)
- ✅ WorkersModule

### M2 — Billing + Invoicing + Checks ✅
- ✅ BillingModule (charge schedules, dry-run preview, cycle generation)
- ✅ DunningService (per-spec escalation policy)
- ✅ PaymentsModule + TranzilaAdapter (live + mock) + webhook handler
- ✅ InvoicingModule (tax-compliant Hebrew, gap-free serials, credit notes)
- ✅ ItaClearanceAdapter (live + mock) for ITA e-invoicing
- ✅ ChecksModule (intake, deposit batches, bounced workflow w/ auto fee)

### M3 — Tickets + Tasks + Documents ✅
- ✅ TicketsModule (intake, AI auto-classification, status workflow, rating)
- ✅ TasksModule (CRUD, assign, status transitions)
- ✅ DocumentsModule (vault upload, versioning, expiring-soon)

### M4 — Mobile + Gate Access ✅
- ✅ AccessModule (one-tap gate open, provider pattern, guest codes)
- ✅ apps/mobile-resident (Expo Router, 5-tab UI, claim QR flow, pay via Tranzila iframe, ticket-new with photos)
- ✅ apps/mobile-maintenance (Today's schedule, navigate, mark done)
- ✅ apps/desktop (Electron wrapper of admin web with auto-update)

### M5 — WhatsApp + AI ✅
- ✅ WhatsAppModule (Cloud API send text + template, webhook receive)
- ✅ AiBotModule (Claude integration with tools, mock fallback, escalation)
- ✅ NotificationsModule (push/email/sms/whatsapp fanout, dedupe, DND)
- ✅ AuditModule (hash-chained audit log)
- ✅ FilesModule (Supabase Storage upload-intent + signed URLs)
- ✅ FlyersModule (welcome flyer with QR — 4 variants per §8)
- ✅ VendorsModule + MASAV file generation
- ✅ BulletinModule (posts + reactions)
- ✅ PollsModule (eligibility per role, HMAC anonymity)
- ✅ AddonsModule (catalog + purchase)
- ✅ ReportsModule (collection rate, AR aging, open tickets, per-person AR)

### M6 — Polish + Marketing GA ✅
- ✅ apps/marketing (Next.js 14, Hebrew RTL, hero + features + who + pricing + testimonials + FAQ + footer + signup page)
- ✅ apps/admin (Next.js 14, Hebrew RTL, login, dashboard with KPIs, buildings list, invoices, checks, documents pages, full sidebar nav)
- ✅ Tests:
  - currency.test.ts (VAT computation, installments split)
  - masav.test.ts (MASAV file structure + totals)
  - classifier.test.ts (Hebrew ticket categorization)
  - assignment.service.test.ts (bill-payer resolution for all 4 scenarios)

## Modules summary

**Total**: 22 NestJS modules, 12 SQL migrations, 6 packages, 5 apps (marketing, admin, mobile-resident, mobile-maintenance, desktop, api).

## Files / modules built so far

```
building-management/
├── SPEC.md                     # 39-section master spec
├── PROGRESS.md                 # this file
├── README.md
├── package.json                # root monorepo
├── turbo.json
├── pnpm-workspace.yaml
├── tsconfig.base.json
├── .env.example
├── .github/workflows/ci.yml
├── apps/
│   ├── api/                    # NestJS — 22 modules, 60+ files
│   ├── admin/                  # Next.js 14 — login + dashboard + 4 critical screens
│   ├── marketing/              # Next.js 14 — Hebrew RTL landing
│   ├── mobile-resident/        # Expo RN — 5 tabs + claim + pay + ticket-new
│   ├── mobile-maintenance/     # Expo RN — today's schedule
│   └── desktop/                # Electron wrapper
└── packages/
    ├── db/                     # 12 SQL migrations + seed + types
    ├── shared/                 # Zod + i18n + currency + masav + templates
    ├── ai/                     # Claude + prompts + tools + classifier
    ├── types/
    └── config/
```

## Human action required (👤)

These cannot be done by the AI agent and need you:

1. ✅ **Create GitHub repo `Building-management`** (done by user)
2. **Extract `building-management/` subdirectory** to the new repo:
   ```
   git clone https://github.com/DudiMaman/Tbot_Claude_5.26.git
   cd Tbot_Claude_5.26
   git checkout claude/hebrew-greeting-Wl7M5
   git subtree split --prefix=building-management -b extract
   git remote add bm git@github.com:DudiMaman/Building-management.git
   git push bm extract:main
   ```
3. **Supabase project** — create at supabase.com, region `eu-west-1` (Frankfurt or Dublin). Fill `SUPABASE_*` env vars.
4. **Tranzila merchant** — open Israeli account at tranzila.com, get supplier id + HMAC secret.
5. **Meta WhatsApp Business** — Business Manager → WhatsApp Business Account → app + system user. Business verification required.
6. **Anthropic API key** — at console.anthropic.com.
7. **Resend** (email) — at resend.com (Israeli IPs preferred).
8. **Inforu** or **019** (SMS) — Israeli SMS gateway account.
9. **Expo account** — for EAS builds of mobile apps.
10. **Apple Developer + Google Play** — for mobile app publishing ($99/yr + $25 one-time).
11. **Domain name** — e.g., `building-management.co.il`, DNS to Vercel/Cloudflare.
12. **Vercel account** — marketing + admin web hosting.
13. **Fly.io or Railway account** — API hosting.
14. **Israel Tax Authority** — apply for e-invoicing access (sandbox first), see https://www.gov.il/he/departments/general/tax-authority-invoice-allocation-numbers
15. **Doppler** — secrets management across envs.
16. **Sentry** — error tracking.
17. **Mapbox or MapLibre** — for the admin map view (Mapbox is paid).

## Known gaps & TODOs (for future sessions)

These are items intentionally stubbed or simplified for the autonomous build:

### High priority
- **PDF generation**: FlyersService and InvoicingService return placeholder URLs. Implement `@react-pdf/renderer` server-side with embedded Hebrew fonts (Heebo, Rubik).
- **Tranzila iframe**: `apps/mobile-resident/app/pay.tsx` uses a placeholder URL — wire to real Tranzila iframe with token callback handler.
- **Supabase Auth wiring**: `apps/admin/src/app/login/page.tsx` is a placeholder form. Wire to `@supabase/ssr`.
- **API client in apps**: admin/mobile apps currently use static data. Add SWR/tRPC client wired to API base URL.
- **Push notifications setup**: Expo Push token registration on mobile not yet wired (need `expo-notifications`).
- **Background job runner**: `BullMQ` queues defined in `app.module.ts` but worker process not yet bootstrapped. Add `apps/api/src/main.worker.ts`.
- **Subscribe to PR webhooks**: ITA clearance, Tranzila notify, WhatsApp messages — webhook controllers exist but need production HMAC secrets.

### Medium priority
- **Admin web pages**: only login + dashboard + buildings + invoices + checks + documents implemented. Need: apartments, people, rental-contracts, tasks, tickets, charges, vendors, bulletin, polls, whatsapp inbox, ai-bot tuning, addons, reports, settings, audit-log.
- **Pino logger integration**: configured in package.json but not yet wired into AppModule.
- **OpenAPI / Swagger**: not exposed yet. Add `@nestjs/swagger`.
- **E2E tests**: Playwright config not set up.
- **i18n on admin**: hardcoded Hebrew strings; should load from `@bm/shared/i18n`.
- **AI bot RAG**: KB chunks table exists but ingestion + retrieval not wired.
- **Polls signature verification**: signature_blob stored but verification logic stubbed.
- **Document OCR**: stubbed — wire to Claude vision for PDFs/images.

### Low priority / nice-to-have
- **English i18n**: Hebrew is primary; English mirror partial.
- **Mapbox integration**: admin map view (§23) stub.
- **Russian/Arabic resident locales**: SPEC §28 mentions them; only Hebrew + English structured.
- **Slack/Discord webhooks for ops alerts**.

## Architecture notes for next session

- **All external integrations have mock adapters** that activate when env vars are missing or `_MODE=mock`. This means the API runs end-to-end without any external credentials.
- **RLS is enforced both at PostgreSQL level AND application level** — every service uses `DbService.withTenantContext()` which sets the JWT claim variables on the connection.
- **The bill-payer resolution algorithm** (§3.6.4) is implemented in `apps/api/src/modules/apartments/assignment.service.ts` and tested in the matching `.test.ts` file with all 4 scenarios from SPEC §3.6.7 (A/B/C/D).
- **Receipt numbering** uses the SQL function `allocate_invoice_serial()` for atomic gap-free serials — won't double-allocate under load.
- **Bounced check workflow**: when a check is marked `bounced`, a DB trigger reverts the related charges; the ChecksService additionally creates a fee charge and a BouncedCheck row.

## Repository extraction note

The intended final home is `https://github.com/DudiMaman/Building-management`. This codebase lives under `building-management/` in the source repo because the AI agent's MCP tools are restricted to the source repo. To extract:

```bash
git subtree split --prefix=building-management -b extract
git push git@github.com:DudiMaman/Building-management.git extract:main
```

This preserves the commit history cleanly.
