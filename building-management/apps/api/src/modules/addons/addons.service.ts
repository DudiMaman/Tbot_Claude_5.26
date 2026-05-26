import { Injectable } from '@nestjs/common';
import { DbService } from '../../db/db.service';

@Injectable()
export class AddonsService {
  constructor(private readonly db: DbService) {}

  async createProduct(tenantId: string, input: { sku: string; name: string; price: number; description?: string; commission_pct?: number; availability_buildings?: string[] }) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const { rows } = await c.query(
        `insert into addon_products (tenant_id, sku, name, description, price, commission_pct, availability_buildings)
         values ($1, $2, $3, $4, $5, $6, $7) returning *`,
        [
          tenantId,
          input.sku,
          input.name,
          input.description ?? null,
          input.price,
          input.commission_pct ?? 0,
          input.availability_buildings ?? [],
        ],
      );
      return rows[0];
    });
  }

  async listForBuilding(tenantId: string, buildingId: string) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const { rows } = await c.query(
        `select * from addon_products
         where status = 'active'
           and ($1 = any(availability_buildings) or availability_buildings = '{}')
         order by name`,
        [buildingId],
      );
      return rows;
    });
  }

  async order(tenantId: string, personId: string, input: { product_id: string; apartment_id: string; building_id: string; qty: number }) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'resident' }, async (c) => {
      const productRes = await c.query<{ price: string }>(
        `select price from addon_products where id = $1`,
        [input.product_id],
      );
      const total = Number(productRes.rows[0]?.price ?? 0) * input.qty;
      const { rows } = await c.query(
        `insert into addon_orders
          (tenant_id, product_id, ordered_by_person_id, building_id, apartment_id, qty, total)
         values ($1, $2, $3, $4, $5, $6, $7) returning *`,
        [tenantId, input.product_id, personId, input.building_id, input.apartment_id, input.qty, total],
      );
      return rows[0];
    });
  }
}
