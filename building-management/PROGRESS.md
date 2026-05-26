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
- ✅ DB schema: tenants, buildings, apartments, people, management_users, maintenance_workers
- ✅ DB schema: apartment_assignments + rental_contracts (the owner/renter/bill-payer model)
- ✅ RLS policies for all tenant-scoped tables
- 🔴 NestJS API modules (in progress next)

### M2 — Billing + Invoicing + Checks
- ✅ DB schema: charge_schedules, charges, payments, payment_methods
- ✅ DB schema: invoices (ITA-clearance-ready), invoice_series, invoice_line_items
- ✅ DB schema: checks, check_batches, bounced_checks (with revert trigger)
- 🔴 Service-layer implementation

### M3 — Tickets + Tasks + Documents
- ✅ DB schema: service_tickets, tasks, ticket_comments
- ✅ DB schema: documents, document_versions, document_acls
- 🔴 Service-layer implementation

### M4 — Mobile Apps + Gate Access
- ✅ DB schema: access_gates, guest_codes, access_events
- 🔴 Mobile apps

### M5 — WhatsApp + AI
- ✅ DB schema: conversations, messages, bot_conversations
- ✅ DB schema: notifications, kb_documents, kb_chunks (pgvector)
- ✅ AI prompts + Claude tools defined
- 🔴 Service-layer + WhatsApp webhook handler

### M6 — Polish + Marketing GA
- 🔴 Marketing site
- 🔴 Admin web

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
