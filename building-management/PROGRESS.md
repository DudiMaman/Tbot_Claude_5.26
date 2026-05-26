# Progress Tracker

This document is updated continuously as development proceeds. It is the source of truth on what is done, what is stubbed, and what needs human action.

> See [`SPEC.md`](./SPEC.md) for the master spec. Section numbers below refer to it.

## Status legend

- ✅ Done & working
- 🟡 Scaffolded / stubbed (compiles, has placeholders / mock adapters)
- 🔴 Not started
- 👤 Requires human action (account, credentials, manual setup)

## Milestone status

### M0 — Foundation
- ✅ Monorepo skeleton (pnpm + Turborepo)
- ✅ Root configs (tsconfig.base, .prettierrc, .gitignore, .env.example)
- ✅ `packages/db` — full Postgres schema (11 migrations, all entities, RLS)
- ✅ `packages/shared` — Zod schemas, i18n, currency, phone, MASAV builder, templates
- ✅ `packages/types` — API contract types
- ✅ `packages/config` — Tailwind preset
- ✅ `packages/ai` — Claude client, prompts, tools, classifier
- 🔴 CI workflows

### M1 — Auth + Core Domain
- ✅ DB schema: all entities, full RLS
- ✅ NestJS bootstrap (main, AppModule, DbModule, HealthController)
- ✅ AuthModule: SupabaseJwtGuard, RlsContextInterceptor, RolesGuard, Public decorator
- ✅ TenantsModule (signup, get, branding)
- ✅ BuildingsModule (CRUD)
- ✅ ApartmentsModule + AssignmentService (resolveBillPayer algorithm — CRITICAL)
- ✅ PeopleModule (CRUD + QR claim flow)
- ✅ WorkersModule (CRUD + today's schedule)

### M2 — Billing + Invoicing + Checks
- ✅ BillingModule + BillingService (charge schedules, dry-run, cycle generation w/ bill-payer resolution)
- ✅ BillingModule + DunningService (per-spec dunning policy)
- ✅ PaymentsModule + Tranzila adapter (live + mock) + webhook handler
- ✅ InvoicingModule (tax-compliant issue + credit notes, gap-free serials, ITA clearance live+mock)
- ✅ ChecksModule (intake, deposit batches, bounce workflow with charge reversal + auto fee)

### M3 — Tickets + Tasks + Documents
- ✅ TicketsModule (intake, AI classifier integration, status workflow, rating)
- ✅ TasksModule (CRUD, assign, status transitions)
- ✅ DocumentsModule (vault upload, versioning, expiring-soon scan)

### M4 — Mobile Apps + Gate Access
- ✅ AccessModule (gate open with provider pattern, http-webhook + mock providers, guest codes)
- 🔴 Mobile apps (next)

### M5 — WhatsApp + AI
- ✅ WhatsAppModule (Cloud API integration, send text + template, webhook receive)
- ✅ AiBotModule (Claude integration with tools, mock fallback, escalation)
- ✅ NotificationsModule (multi-channel fanout: push/email/sms/whatsapp, dedupe, DND)
- ✅ AuditModule (hash-chained audit log)
- ✅ FilesModule (Supabase storage upload-intent + signed URLs)
- ✅ FlyersModule (welcome flyer with QR for 4 variants)
- ✅ VendorsModule + MASAV file generation
- ✅ BulletinModule (posts + reactions)
- ✅ PollsModule (with eligibility checks per role, anonymous hashing)
- ✅ AddonsModule (catalog + purchase flow)
- ✅ ReportsModule (collection rate, AR aging, open tickets, per-person AR)

### M6 — Polish + Marketing GA
- 🔴 Marketing site (next)
- 🔴 Admin web (next)
- 🔴 Mobile apps (next)
- 🔴 Tests

## Human action required (👤)

These cannot be done by the AI agent and need you:

1. **Create GitHub repo** `Building-management` (private or public).
2. **Supabase project** — create at supabase.com, region `eu-west-1`. Fill `SUPABASE_*` env vars.
3. **Tranzila merchant** — open Israeli account at tranzila.com, get supplier id + HMAC.
4. **Meta WhatsApp Business** — Business Manager → WhatsApp Business Account → app + system user. Business verification required.
5. **Anthropic API key** — at console.anthropic.com.
6. **Resend** (email) — at resend.com.
7. **Inforu / 019** (SMS) — Israeli SMS gateway accounts.
8. **Expo account** — for EAS builds of mobile apps.
9. **Apple Developer + Google Play** — for mobile app publishing.
10. **Domain name** — e.g., `your-domain.co.il`, with DNS pointing to Vercel/Cloudflare.
11. **Vercel account** — for marketing + admin web hosting.
12. **Fly.io or Railway account** — for API hosting.
13. **Israel Tax Authority** — apply for e-invoicing access (sandbox first).
14. **Doppler** — secrets management across envs.
15. **Sentry** — error tracking.

Until 1 is done, code is committed to the host repo under `building-management/` directory.

## Files / modules built so far

(populated as work progresses)
