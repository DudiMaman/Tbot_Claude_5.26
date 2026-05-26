# Building Management — Israeli SaaS CRM

A modern, Hebrew-first SaaS platform for Israeli building management companies. Replaces and exceeds Darimpo, Bllink, and Build-app.

> This project sits under `building-management/` inside the host repository for development convenience. The intended final home is a standalone GitHub repository named `Building-management`. Use `git subtree split` to extract.

## What's inside

A monorepo (Turborepo + pnpm) containing:

- `apps/marketing/` — Next.js 14 marketing site (Hebrew RTL)
- `apps/admin/` — Next.js 14 admin web for management companies
- `apps/mobile-resident/` — Expo RN app for residents (owners + renters)
- `apps/mobile-maintenance/` — Expo RN app for maintenance workers
- `apps/desktop/` — Electron wrapper of admin web
- `apps/api/` — NestJS 10 API + workers
- `packages/db/` — Postgres schema + Supabase migrations + Prisma client
- `packages/shared/` — Pure TS types, Zod schemas, templates
- `packages/ui/` — shadcn-based component library
- `packages/types/` — Codegen types
- `packages/ai/` — Claude prompts + tools + RAG
- `packages/config/` — Shared eslint/tsconfig/tailwind presets

## Tech

- **Mobile**: React Native + Expo SDK 51
- **Backend**: Node.js 20 + NestJS 10 + TypeScript 5
- **DB**: Postgres 15 via Supabase (eu-west-1)
- **Payments**: Tranzila (with mock adapter for local dev)
- **AI**: Anthropic Claude (`claude-sonnet-4-6`)
- **WhatsApp**: Meta WhatsApp Business Cloud API (direct)
- **Multi-tenancy**: shared DB + `tenant_id` + Postgres RLS

## Quick start

```bash
pnpm install
cp .env.example .env
# fill in credentials (see SPEC.md §36)
pnpm db:migrate
pnpm db:seed
pnpm dev
```

## Documentation

The full master specification is at [`SPEC.md`](./SPEC.md) — read it first.
Progress is tracked at [`PROGRESS.md`](./PROGRESS.md).
