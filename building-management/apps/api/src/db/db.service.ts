import { Injectable, OnModuleDestroy, OnModuleInit, Logger } from '@nestjs/common';
import { getPool, setRlsContext, withTransaction } from '@bm/db';
import type { PoolClient } from 'pg';

@Injectable()
export class DbService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(DbService.name);

  async onModuleInit() {
    try {
      const pool = getPool();
      const res = await pool.query('select 1 as ok');
      this.logger.log(`DB connected (ok=${res.rows[0]?.ok})`);
    } catch (err) {
      this.logger.error(`DB connection failed: ${(err as Error).message}`);
    }
  }

  async onModuleDestroy() {
    try {
      await getPool().end();
    } catch {
      // ignore
    }
  }

  /**
   * Run a function inside a transaction with RLS context set.
   * Use this for any operation that touches tenant data.
   */
  async withTenantContext<T>(
    claims: { tenant_id: string; role?: string; person_id?: string; sub?: string },
    fn: (client: PoolClient) => Promise<T>,
  ): Promise<T> {
    return withTransaction(async (client) => {
      await setRlsContext(client, claims);
      return fn(client);
    });
  }

  /** Read-only convenience: pool query (no RLS — admin use only). */
  async query<T = unknown>(sql: string, params?: unknown[]) {
    return getPool().query<T>(sql, params as never);
  }
}
