/**
 * AuditService — append-only, hash-chained for tamper-evidence.
 * See SPEC §24.
 */
import { Injectable } from '@nestjs/common';
import { createHash } from 'node:crypto';
import { DbService } from '../../db/db.service';

@Injectable()
export class AuditService {
  constructor(private readonly db: DbService) {}

  async log(input: {
    tenant_id: string;
    actor_user_id?: string;
    actor_type?: string;
    action: string;
    entity_type: string;
    entity_id?: string;
    before?: unknown;
    after?: unknown;
    ip?: string;
    user_agent?: string;
  }) {
    // Fetch the latest hash for the tenant
    const prev = await this.db.query<{ this_hash: string }>(
      `select this_hash from audit_log where tenant_id = $1 order by created_at desc limit 1`,
      [input.tenant_id],
    );
    const prevHash = prev.rows[0]?.this_hash ?? '';
    const payload = JSON.stringify({
      tenant_id: input.tenant_id,
      action: input.action,
      entity_type: input.entity_type,
      entity_id: input.entity_id ?? null,
      before: input.before ?? null,
      after: input.after ?? null,
    });
    const thisHash = createHash('sha256').update(prevHash + payload).digest('hex');

    await this.db.query(
      `insert into audit_log
        (tenant_id, actor_user_id, actor_type, action, entity_type, entity_id,
         before_json, after_json, ip, user_agent, prev_hash, this_hash)
       values ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9, $10, $11, $12)`,
      [
        input.tenant_id,
        input.actor_user_id ?? null,
        input.actor_type ?? 'system',
        input.action,
        input.entity_type,
        input.entity_id ?? null,
        JSON.stringify(input.before ?? null),
        JSON.stringify(input.after ?? null),
        input.ip ?? null,
        input.user_agent ?? null,
        prevHash,
        thisHash,
      ],
    );
  }

  async list(tenantId: string, entityType?: string, entityId?: string) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const conds: string[] = [];
      const params: any[] = [];
      if (entityType) { params.push(entityType); conds.push(`entity_type = $${params.length}`); }
      if (entityId) { params.push(entityId); conds.push(`entity_id = $${params.length}`); }
      const where = conds.length ? `where ${conds.join(' and ')}` : '';
      const { rows } = await c.query(
        `select * from audit_log ${where} order by created_at desc limit 200`,
        params,
      );
      return rows;
    });
  }
}
