import { Injectable, NotFoundException } from '@nestjs/common';
import { DbService } from '../../db/db.service';
import { classifyTicket } from '@bm/ai';
import type { CreateTicket } from '@bm/shared';
import type { ServiceTicket } from '@bm/db';

@Injectable()
export class TicketsService {
  constructor(private readonly db: DbService) {}

  async create(tenantId: string, openedByPersonId: string | null, input: CreateTicket): Promise<ServiceTicket> {
    // Auto-classify if category=other
    let category = input.category;
    let priority = input.priority;
    if (category === 'other') {
      const result = await classifyTicket(input.description ?? input.title, input.photos);
      category = result.category;
      if (priority === 'med') priority = result.priority;
    }

    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const { rows } = await c.query<ServiceTicket>(
        `insert into service_tickets
          (tenant_id, building_id, apartment_id, opened_by_person_id, intake_channel,
           title, description, category, priority, photos, status, opened_at)
         values ($1, $2, $3, $4, 'app', $5, $6, $7, $8, $9::jsonb, 'new', now())
         returning *`,
        [
          tenantId,
          input.building_id,
          input.apartment_id ?? null,
          openedByPersonId,
          input.title,
          input.description ?? null,
          category,
          priority,
          JSON.stringify(input.photos),
        ],
      );
      return rows[0]!;
    });
  }

  async list(tenantId: string, buildingId?: string, status?: string) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const conds: string[] = [];
      const params: any[] = [];
      if (buildingId) { params.push(buildingId); conds.push(`building_id = $${params.length}`); }
      if (status) { params.push(status); conds.push(`status = $${params.length}`); }
      const where = conds.length ? `where ${conds.join(' and ')}` : '';
      const { rows } = await c.query(
        `select * from service_tickets ${where} order by opened_at desc`,
        params,
      );
      return rows;
    });
  }

  async findOne(tenantId: string, id: string): Promise<ServiceTicket> {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const { rows } = await c.query<ServiceTicket>(`select * from service_tickets where id = $1`, [id]);
      if (rows.length === 0) throw new NotFoundException();
      return rows[0]!;
    });
  }

  async updateStatus(tenantId: string, id: string, status: ServiceTicket['status'], note?: string) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const extras: string[] = [];
      const params: any[] = [id, status];
      if (status === 'resolved') extras.push(`resolved_at = now()`);
      if (status === 'closed') extras.push(`closed_at = now()`);
      if (note) { params.push(note); extras.push(`resolution_note = $${params.length}`); }
      const setExtra = extras.length ? `, ${extras.join(', ')}` : '';
      const { rows } = await c.query<ServiceTicket>(
        `update service_tickets set status = $2 ${setExtra} where id = $1 returning *`,
        params,
      );
      if (rows.length === 0) throw new NotFoundException();
      return rows[0]!;
    });
  }

  async rate(tenantId: string, id: string, rating: number, comment?: string) {
    if (rating < 1 || rating > 5) throw new Error('rating 1-5');
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'resident' }, async (c) => {
      await c.query(`update service_tickets set satisfaction_rating = $2 where id = $1`, [id, rating]);
      if (comment) {
        await c.query(
          `insert into ticket_comments (tenant_id, ticket_id, body, visibility) values ($1, $2, $3, 'resident')`,
          [tenantId, id, comment],
        );
      }
      return { ok: true };
    });
  }
}
