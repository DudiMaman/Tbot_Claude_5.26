import { Injectable, NotFoundException } from '@nestjs/common';
import { DbService } from '../../db/db.service';
import type { CreateBuilding } from '@bm/shared';
import type { Building } from '@bm/db';

@Injectable()
export class BuildingsService {
  constructor(private readonly db: DbService) {}

  async create(tenantId: string, input: CreateBuilding): Promise<Building> {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      const geoExpr =
        input.geo_lat !== undefined && input.geo_lng !== undefined
          ? `ST_SetSRID(ST_MakePoint($9, $10), 4326)::geography`
          : 'null';
      const params: any[] = [
        tenantId,
        input.name,
        input.address_line,
        input.city,
        input.postal_code ?? null,
        input.num_floors ?? null,
        input.num_apartments ?? null,
        input.year_built ?? null,
      ];
      if (input.geo_lng !== undefined && input.geo_lat !== undefined) {
        params.push(input.geo_lng, input.geo_lat);
      }
      const { rows } = await client.query<Building>(
        `insert into buildings
          (tenant_id, name, address_line, city, postal_code, num_floors, num_apartments, year_built, geo)
         values ($1, $2, $3, $4, $5, $6, $7, $8, ${geoExpr})
         returning *`,
        params,
      );
      return rows[0]!;
    });
  }

  async list(tenantId: string) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      const { rows } = await client.query(
        `select b.*,
                (select count(*) from apartments a where a.building_id = b.id and a.deleted_at is null) as apartment_count,
                (select count(*) from service_tickets st where st.building_id = b.id and st.status not in ('resolved','closed')) as open_tickets
         from buildings b
         where deleted_at is null
         order by created_at desc`,
      );
      return rows;
    });
  }

  async findOne(tenantId: string, id: string): Promise<Building> {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      const { rows } = await client.query<Building>(
        `select * from buildings where id = $1 and deleted_at is null`,
        [id],
      );
      if (rows.length === 0) throw new NotFoundException('Building not found');
      return rows[0]!;
    });
  }

  async update(tenantId: string, id: string, patch: Partial<CreateBuilding>) {
    const sets: string[] = [];
    const params: any[] = [id];
    let i = 1;
    for (const [k, v] of Object.entries(patch)) {
      if (v === undefined) continue;
      i++;
      params.push(v);
      sets.push(`${k} = $${i}`);
    }
    if (sets.length === 0) return this.findOne(tenantId, id);
    sets.push('updated_at = now()');
    await this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      await client.query(`update buildings set ${sets.join(', ')} where id = $1`, params);
    });
    return this.findOne(tenantId, id);
  }

  async softDelete(tenantId: string, id: string) {
    await this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      await client.query(`update buildings set deleted_at = now() where id = $1`, [id]);
    });
    return { ok: true };
  }
}
