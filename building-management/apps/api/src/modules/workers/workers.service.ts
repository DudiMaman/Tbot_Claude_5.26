import { Injectable, NotFoundException } from '@nestjs/common';
import { DbService } from '../../db/db.service';
import type { MaintenanceWorker } from '@bm/db';

@Injectable()
export class WorkersService {
  constructor(private readonly db: DbService) {}

  async create(
    tenantId: string,
    input: {
      full_name: string;
      phone_e164: string;
      email?: string;
      skills?: string[];
      employment_type?: 'employee' | 'contractor';
      hourly_rate?: number;
    },
  ): Promise<MaintenanceWorker> {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const { rows } = await c.query<MaintenanceWorker>(
        `insert into maintenance_workers (tenant_id, full_name, phone_e164, email, skills, employment_type, hourly_rate)
         values ($1, $2, $3, $4, $5::jsonb, $6, $7) returning *`,
        [
          tenantId,
          input.full_name,
          input.phone_e164,
          input.email ?? null,
          JSON.stringify(input.skills ?? []),
          input.employment_type ?? 'employee',
          input.hourly_rate ?? null,
        ],
      );
      return rows[0]!;
    });
  }

  async list(tenantId: string) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const { rows } = await c.query(
        `select * from maintenance_workers where deleted_at is null order by full_name`,
      );
      return rows;
    });
  }

  async assignToBuilding(tenantId: string, workerId: string, buildingId: string) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      await c.query(
        `insert into worker_building_assignments (tenant_id, worker_id, building_id)
         values ($1, $2, $3) on conflict do nothing`,
        [tenantId, workerId, buildingId],
      );
      return { ok: true };
    });
  }

  async todaySchedule(tenantId: string, workerId: string) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const { rows } = await c.query(
        `select * from tasks
         where assigned_worker_id = $1
           and status in ('todo','in_progress','blocked')
         order by scheduled_at nulls last, priority desc`,
        [workerId],
      );
      return rows;
    });
  }
}
