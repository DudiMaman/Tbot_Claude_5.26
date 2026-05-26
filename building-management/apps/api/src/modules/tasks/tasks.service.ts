import { Injectable, NotFoundException } from '@nestjs/common';
import { DbService } from '../../db/db.service';
import type { Task } from '@bm/db';

@Injectable()
export class TasksService {
  constructor(private readonly db: DbService) {}

  async create(
    tenantId: string,
    input: {
      building_id: string;
      apartment_id?: string;
      title: string;
      description_md?: string;
      category?: string;
      priority?: 'low' | 'med' | 'high' | 'urgent';
      assigned_worker_id?: string;
      scheduled_at?: string;
      source?: 'planned' | 'ticket' | 'adhoc';
      source_ticket_id?: string;
      customer_visible?: boolean;
    },
  ): Promise<Task> {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const { rows } = await c.query<Task>(
        `insert into tasks
          (tenant_id, building_id, apartment_id, source, source_ticket_id, title, description_md,
           category, priority, assigned_worker_id, scheduled_at, customer_visible)
         values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
         returning *`,
        [
          tenantId,
          input.building_id,
          input.apartment_id ?? null,
          input.source ?? 'adhoc',
          input.source_ticket_id ?? null,
          input.title,
          input.description_md ?? null,
          input.category ?? 'other',
          input.priority ?? 'med',
          input.assigned_worker_id ?? null,
          input.scheduled_at ?? null,
          input.customer_visible ?? true,
        ],
      );
      return rows[0]!;
    });
  }

  async list(tenantId: string, params: { worker_id?: string; building_id?: string; status?: string } = {}) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const conds: string[] = [];
      const sqlParams: any[] = [];
      if (params.worker_id) { sqlParams.push(params.worker_id); conds.push(`assigned_worker_id = $${sqlParams.length}`); }
      if (params.building_id) { sqlParams.push(params.building_id); conds.push(`building_id = $${sqlParams.length}`); }
      if (params.status) { sqlParams.push(params.status); conds.push(`status = $${sqlParams.length}`); }
      const where = conds.length ? `where ${conds.join(' and ')}` : '';
      const { rows } = await c.query<Task>(
        `select * from tasks ${where} order by scheduled_at nulls last, priority desc`,
        sqlParams,
      );
      return rows;
    });
  }

  async updateStatus(tenantId: string, id: string, status: Task['status']) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const setExtra: string[] = [];
      if (status === 'in_progress') setExtra.push(`started_at = coalesce(started_at, now())`);
      if (status === 'done') setExtra.push(`completed_at = now()`);
      const extra = setExtra.length ? `, ${setExtra.join(', ')}` : '';
      const { rows } = await c.query<Task>(
        `update tasks set status = $2 ${extra} where id = $1 returning *`,
        [id, status],
      );
      if (rows.length === 0) throw new NotFoundException();
      return rows[0]!;
    });
  }

  async assign(tenantId: string, id: string, workerId: string) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const { rows } = await c.query<Task>(
        `update tasks set assigned_worker_id = $2, status = case when status = 'todo' then 'todo' else status end where id = $1 returning *`,
        [id, workerId],
      );
      if (rows.length === 0) throw new NotFoundException();
      return rows[0]!;
    });
  }
}
