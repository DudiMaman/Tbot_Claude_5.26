/**
 * InvoicingService — issuance of tax-compliant Hebrew invoices.
 *
 * Key invariants (SPEC §37):
 *  - Numbering: gap-free sequential per (tenant, type), assigned atomically
 *    by allocate_invoice_serial() SQL function.
 *  - ITA clearance: requested when total >= threshold.
 *  - Cancellation: never edit issued invoices — issue credit notes.
 *  - Customer snapshots: name/address/vat_id frozen at issuance.
 */
import { Injectable, Logger, NotFoundException, BadRequestException } from '@nestjs/common';
import { DbService } from '../../db/db.service';
import { ItaClearanceAdapter } from './ita-clearance.adapter';
import { computeVat } from '@bm/shared';
import type { IssueInvoice } from '@bm/shared';
import type { Invoice } from '@bm/db';

@Injectable()
export class InvoicingService {
  private readonly logger = new Logger(InvoicingService.name);

  constructor(
    private readonly db: DbService,
    private readonly ita: ItaClearanceAdapter,
  ) {}

  async issue(tenantId: string, actorUserId: string, input: IssueInvoice): Promise<Invoice> {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      // Compute totals
      let subtotal = 0;
      let vatTotal = 0;
      const lineItems = input.line_items.map((li, position) => {
        const itemSubtotal = li.quantity * li.unit_price;
        const vat = computeVat(itemSubtotal, 'exclusive', li.vat_rate_pct);
        subtotal += vat.subtotal;
        vatTotal += vat.vat;
        return {
          position,
          description: li.description,
          quantity: li.quantity,
          unit_price: li.unit_price,
          subtotal: vat.subtotal,
          vat_rate_pct: li.vat_rate_pct,
          vat_amount: vat.vat,
          total: vat.total,
        };
      });
      const total = subtotal + vatTotal;

      // Series
      const seriesRes = await client.query<{ document_type: string }>(
        `select document_type from invoice_series where id = $1`,
        [input.series_id],
      );
      if (seriesRes.rows.length === 0) throw new NotFoundException('Invoice series not found');
      const docType = seriesRes.rows[0]!.document_type as Invoice['type'];

      // Fetch customer + tenant for snapshots
      const personRes = await client.query<{ full_name: string; email: string | null }>(
        `select full_name, email from people where id = $1`,
        [input.customer_person_id],
      );
      if (personRes.rows.length === 0) throw new NotFoundException('Customer not found');
      const tenantRes = await client.query<{ vat_id: string | null; legal_name: string | null }>(
        `select vat_id, legal_name from tenants where id = $1`,
        [tenantId],
      );

      // ITA clearance (only for tax invoices and combined; receipt-only is exempt)
      let itaStatus: Invoice['ita_clearance_status'] = 'not_required';
      let allocation: string | null = null;
      if (docType !== 'receipt') {
        const clearance = await this.ita.request({
          tenant_vat_id: tenantRes.rows[0]?.vat_id ?? '',
          customer_vat_id: null,
          invoice_type: docType === 'credit_note' ? 'credit_note' : 'tax_invoice',
          invoice_total_ils: total,
          invoice_date: new Date().toISOString().slice(0, 10),
        });
        if (clearance.required && clearance.status === 'rejected') {
          throw new BadRequestException(`ITA clearance rejected: ${clearance.rejection_reason}`);
        }
        itaStatus = clearance.status;
        allocation = clearance.allocation_number ?? null;
      }

      // Allocate sequential serial
      const serialRes = await client.query<{ allocate_invoice_serial: number }>(
        `select allocate_invoice_serial($1) as allocate_invoice_serial`,
        [input.series_id],
      );
      const serialNumber = serialRes.rows[0]!.allocate_invoice_serial;

      // Insert invoice
      const { rows } = await client.query<Invoice>(
        `insert into invoices
          (tenant_id, series_id, type, serial_number, status, issued_at, issued_by_user_id,
           customer_person_id, customer_name_snapshot,
           description, currency, subtotal, vat_rate_pct, vat_amount, total,
           related_charge_ids, related_payment_ids,
           ita_clearance_status, ita_allocation_number)
         values ($1, $2, $3, $4, 'issued', now(), $5, $6, $7, $8, 'ILS', $9, 17, $10, $11, $12, $13, $14, $15)
         returning *`,
        [
          tenantId,
          input.series_id,
          docType,
          serialNumber,
          actorUserId,
          input.customer_person_id,
          personRes.rows[0]!.full_name,
          input.description ?? null,
          subtotal,
          vatTotal,
          total,
          input.charge_ids ?? [],
          input.payment_ids ?? [],
          itaStatus,
          allocation,
        ],
      );
      const invoice = rows[0]!;

      // Line items
      for (const li of lineItems) {
        await client.query(
          `insert into invoice_line_items
            (tenant_id, invoice_id, position, description, quantity, unit_price,
             subtotal, vat_rate_pct, vat_amount, total)
           values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)`,
          [
            tenantId,
            invoice.id,
            li.position,
            li.description,
            li.quantity,
            li.unit_price,
            li.subtotal,
            li.vat_rate_pct,
            li.vat_amount,
            li.total,
          ],
        );
      }

      // Link related charges
      if (input.charge_ids && input.charge_ids.length > 0) {
        await client.query(
          `update charges set invoice_id = $1, invoice_number = $2 where id = any($3::uuid[])`,
          [invoice.id, String(serialNumber), input.charge_ids],
        );
      }
      return invoice;
    });
  }

  /**
   * Issue a credit note that reverses a previously-issued invoice.
   */
  async issueCreditNote(
    tenantId: string,
    actorUserId: string,
    originalInvoiceId: string,
    seriesId: string,
  ): Promise<Invoice> {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      const origRes = await client.query<Invoice>(
        `select * from invoices where id = $1`,
        [originalInvoiceId],
      );
      if (origRes.rows.length === 0) throw new NotFoundException('Original invoice not found');
      const orig = origRes.rows[0]!;
      if (orig.status === 'cancelled') throw new BadRequestException('Already cancelled');

      const serialRes = await client.query<{ allocate_invoice_serial: number }>(
        `select allocate_invoice_serial($1) as allocate_invoice_serial`,
        [seriesId],
      );
      const serialNumber = serialRes.rows[0]!.allocate_invoice_serial;

      const { rows } = await client.query<Invoice>(
        `insert into invoices
          (tenant_id, series_id, type, serial_number, status, issued_at, issued_by_user_id,
           customer_person_id, customer_name_snapshot,
           description, currency, subtotal, vat_rate_pct, vat_amount, total,
           credit_note_for_invoice_id, ita_clearance_status)
         values ($1, $2, 'credit_note', $3, 'issued', now(), $4, $5, $6, $7, 'ILS',
                 $8, $9, $10, $11, $12, 'not_required')
         returning *`,
        [
          tenantId,
          seriesId,
          serialNumber,
          actorUserId,
          orig.customer_person_id,
          orig.customer_name_snapshot,
          `זיכוי בגין חשבונית ${orig.serial_number}`,
          // Negate values for credit note
          -Number(orig.subtotal),
          orig.vat_rate_pct,
          -Number(orig.vat_amount),
          -Number(orig.total),
          orig.id,
        ],
      );
      // Mark original as replaced
      await client.query(`update invoices set status = 'replaced' where id = $1`, [orig.id]);
      return rows[0]!;
    });
  }

  async list(tenantId: string, customerId?: string) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      const { rows } = customerId
        ? await client.query(
            `select * from invoices where customer_person_id = $1 order by issued_at desc nulls last`,
            [customerId],
          )
        : await client.query(`select * from invoices order by issued_at desc nulls last`);
      return rows;
    });
  }

  async getSeries(tenantId: string) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      const { rows } = await client.query(`select * from invoice_series order by document_type`);
      return rows;
    });
  }
}
