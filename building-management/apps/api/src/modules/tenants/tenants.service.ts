import { Injectable, NotFoundException } from '@nestjs/common';
import { DbService } from '../../db/db.service';
import type { CreateTenant } from '@bm/shared';
import type { Tenant } from '@bm/db';

@Injectable()
export class TenantsService {
  constructor(private readonly db: DbService) {}

  /**
   * Tenant signup. Public endpoint — does NOT require an existing tenant_id.
   * Creates Tenant row + initial mgmt_admin row + invoice series.
   */
  async signup(input: CreateTenant & { admin_user_id: string }): Promise<Tenant> {
    const res = await this.db.query<Tenant>(
      `insert into tenants (name, legal_name, vat_id, billing_email, plan, trial_ends_at)
       values ($1, $2, $3, $4, 'trial', now() + interval '30 days')
       returning *`,
      [input.name, input.legal_name ?? null, input.vat_id ?? null, input.billing_email],
    );
    const tenant = res.rows[0]!;

    // Create initial mgmt_admin
    await this.db.query(
      `insert into management_users (tenant_id, full_name, email, role, supabase_user_id)
       values ($1, $2, $3, 'mgmt_admin', $4)`,
      [tenant.id, input.name, input.billing_email, input.admin_user_id],
    );

    // Seed default invoice series
    await this.db.query(
      `insert into invoice_series (tenant_id, document_type, name, prefix, next_serial)
       values ($1, 'tax_invoice_receipt', 'חשבונית מס/קבלה', 'INV', 1),
              ($1, 'credit_note', 'חשבונית זיכוי', 'CN', 1),
              ($1, 'tax_invoice', 'חשבונית מס', 'TI', 1),
              ($1, 'receipt', 'קבלה', 'R', 1)`,
      [tenant.id],
    );

    return tenant;
  }

  async findOne(tenantId: string): Promise<Tenant> {
    const { rows } = await this.db.query<Tenant>(
      `select * from tenants where id = $1`,
      [tenantId],
    );
    if (rows.length === 0) throw new NotFoundException('Tenant not found');
    return rows[0]!;
  }

  async updateBranding(tenantId: string, branding: Record<string, unknown>) {
    await this.db.query(
      `update tenants set branding = $2, updated_at = now() where id = $1`,
      [tenantId, JSON.stringify(branding)],
    );
  }
}
