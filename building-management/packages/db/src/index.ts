/**
 * @bm/db — Postgres client + types for Building Management.
 *
 * The real Prisma client is generated into ./prisma after running
 *   pnpm --filter @bm/db prisma:generate
 * which requires a live DB. For now we export a thin pg-based client and
 * placeholder types used by the rest of the monorepo so it compiles.
 */

import { Pool, type PoolClient } from 'pg';

export interface DbConfig {
  url: string;
  max?: number;
  ssl?: boolean;
}

let pool: Pool | undefined;

export function getPool(config?: DbConfig): Pool {
  if (pool) return pool;
  const url = config?.url ?? process.env.SUPABASE_DB_URL;
  if (!url) {
    throw new Error('SUPABASE_DB_URL is not set');
  }
  pool = new Pool({
    connectionString: url,
    max: config?.max ?? 10,
    ssl: config?.ssl ?? false,
  });
  return pool;
}

export async function withTransaction<T>(
  fn: (client: PoolClient) => Promise<T>,
): Promise<T> {
  const client = await getPool().connect();
  try {
    await client.query('begin');
    const result = await fn(client);
    await client.query('commit');
    return result;
  } catch (err) {
    await client.query('rollback');
    throw err;
  } finally {
    client.release();
  }
}

/**
 * Sets the JWT claims for the current connection so RLS policies fire.
 * Must be called inside a transaction before any query.
 */
export async function setRlsContext(
  client: PoolClient,
  claims: {
    tenant_id: string;
    role?: string;
    person_id?: string;
    sub?: string;
  },
): Promise<void> {
  await client.query(
    `select set_config('request.jwt.claim.tenant_id', $1, true)`,
    [claims.tenant_id],
  );
  if (claims.role) {
    await client.query(
      `select set_config('request.jwt.claim.role', $1, true)`,
      [claims.role],
    );
  }
  if (claims.person_id) {
    await client.query(
      `select set_config('request.jwt.claim.person_id', $1, true)`,
      [claims.person_id],
    );
  }
  if (claims.sub) {
    await client.query(
      `select set_config('request.jwt.claim.sub', $1, true)`,
      [claims.sub],
    );
  }
}

export type {
  Tenant,
  Building,
  Apartment,
  Person,
  ManagementUser,
  MaintenanceWorker,
  ApartmentAssignment,
  RentalContract,
  ChargeSchedule,
  Charge,
  Payment,
  PaymentMethod,
  Invoice,
  InvoiceSeries,
  Check,
  CheckBatch,
  BouncedCheck,
  Document,
  DocumentVersion,
  ServiceTicket,
  Task,
  Vendor,
  BulletinPost,
  Poll,
  Vote,
  Conversation,
  Message,
  Notification,
  AccessGate,
  AddonProduct,
  AddonOrder,
} from './types';
