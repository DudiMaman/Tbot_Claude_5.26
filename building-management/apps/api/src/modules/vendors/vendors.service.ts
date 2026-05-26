import { Injectable } from '@nestjs/common';
import { DbService } from '../../db/db.service';
import { buildMasavFile, type MasavPayment } from '@bm/shared/masav';

@Injectable()
export class VendorsService {
  constructor(private readonly db: DbService) {}

  async create(tenantId: string, input: { name: string; phone?: string; email?: string; iban?: string; services?: string[] }) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const { rows } = await c.query(
        `insert into vendors (tenant_id, name, phone, email, iban, services) values ($1,$2,$3,$4,$5,$6::jsonb) returning *`,
        [tenantId, input.name, input.phone ?? null, input.email ?? null, input.iban ?? null, JSON.stringify(input.services ?? [])],
      );
      return rows[0];
    });
  }

  async list(tenantId: string) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const { rows } = await c.query(`select * from vendors where deleted_at is null order by name`);
      return rows;
    });
  }

  async uploadInvoice(tenantId: string, input: { vendor_id: string; amount: number; vat_amount: number; file_id: string; invoice_number?: string; issue_date?: string; due_date?: string }) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const { rows } = await c.query(
        `insert into vendor_invoices (tenant_id, vendor_id, amount, vat_amount, file_id, invoice_number, issue_date, due_date)
         values ($1,$2,$3,$4,$5,$6,$7,$8) returning *`,
        [
          tenantId,
          input.vendor_id,
          input.amount,
          input.vat_amount,
          input.file_id,
          input.invoice_number ?? null,
          input.issue_date ?? null,
          input.due_date ?? null,
        ],
      );
      return rows[0];
    });
  }

  /** Generate a MASAV payout file for a batch of vendor invoices. */
  async generateMasav(tenantId: string, invoiceIds: string[], payer: { bank_code: string; branch_code: string; account_number: string; name: string }, institutionCode: string) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const { rows } = await c.query<{
        vendor_id: string;
        amount: string;
        bank_code: string | null;
        branch_code: string | null;
        account_number: string | null;
        name: string;
      }>(
        `select vi.vendor_id, vi.amount,
                regexp_replace(v.iban, '\\D', '', 'g') as iban_digits,
                substring(v.iban, 5, 3) as bank_code,
                substring(v.iban, 8, 3) as branch_code,
                substring(v.iban, 11) as account_number,
                v.name
         from vendor_invoices vi
         join vendors v on v.id = vi.vendor_id
         where vi.id = any($1::uuid[])`,
        [invoiceIds],
      );
      const payments: MasavPayment[] = rows.map((r) => ({
        payee: {
          bank_code: r.bank_code ?? '000',
          branch_code: r.branch_code ?? '000',
          account_number: r.account_number ?? '000000',
          name: r.name.slice(0, 16),
        },
        amount_ils: Number(r.amount),
      }));
      const file = buildMasavFile({
        payer,
        file_date: new Date(),
        institution_code: institutionCode,
        payments,
      });
      return { file, payments_count: payments.length };
    });
  }
}
