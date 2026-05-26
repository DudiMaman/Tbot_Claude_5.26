import { Injectable, Logger, NotFoundException, BadRequestException } from '@nestjs/common';
import { DbService } from '../../db/db.service';
import { TranzilaAdapter } from './tranzila.adapter';
import type { CreatePayment } from '@bm/shared';
import type { Charge, Payment, PaymentMethod } from '@bm/db';

@Injectable()
export class PaymentsService {
  private readonly logger = new Logger(PaymentsService.name);

  constructor(
    private readonly db: DbService,
    private readonly tranzila: TranzilaAdapter,
  ) {}

  /**
   * Resident-initiated payment of a charge.
   * Resolves the payment method, calls Tranzila, persists Payment row.
   */
  async payCharge(
    tenantId: string,
    payerPersonId: string,
    input: CreatePayment,
  ): Promise<Payment> {
    const charge = await this.fetchCharge(tenantId, input.charge_id);
    if (charge.status === 'paid') {
      throw new BadRequestException('Charge already paid');
    }
    const method = input.payment_method_id
      ? await this.fetchPaymentMethod(tenantId, input.payment_method_id)
      : await this.fetchDefaultPaymentMethod(tenantId, payerPersonId);
    if (!method || !method.tranzila_token) {
      throw new BadRequestException('No payment method on file');
    }

    const idempotencyKey = `${input.charge_id}_${Date.now()}`;
    const result = await this.tranzila.chargeToken({
      token: method.tranzila_token,
      amountIls: input.amount,
      currency: 'ILS',
      installments: input.installments,
      description: charge.description ?? undefined,
      idempotencyKey,
    });

    return this.db.withTenantContext({ tenant_id: tenantId, role: 'resident' }, async (client) => {
      const { rows } = await client.query<Payment>(
        `insert into payments
          (tenant_id, charge_id, paid_by_person_id, payment_method_id, method,
           amount, currency, status, tranzila_token_id, tranzila_txn_id,
           last4, brand, installments, captured_at, failure_reason, raw_provider_json)
         values ($1, $2, $3, $4, 'card', $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
         returning *`,
        [
          tenantId,
          input.charge_id,
          payerPersonId,
          method.id,
          input.amount,
          'ILS',
          result.ok ? 'captured' : 'failed',
          method.tranzila_token,
          result.txnId ?? null,
          method.last4,
          method.brand,
          input.installments,
          result.ok ? new Date() : null,
          result.failureReason ?? null,
          JSON.stringify(result.raw),
        ],
      );
      return rows[0]!;
    });
  }

  /**
   * Record an offline payment (cash/check/wire).
   * Used by mgmt when reconciling offline collections.
   */
  async recordOfflinePayment(
    tenantId: string,
    actorUserId: string,
    chargeId: string,
    method: 'cash' | 'check' | 'wire' | 'other',
    amount: number,
    notes?: string,
  ): Promise<Payment> {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      const { rows } = await client.query<Payment>(
        `insert into payments
          (tenant_id, charge_id, paid_by_person_id, method, amount, currency, status, captured_at, raw_provider_json)
         values ($1, $2, null, $3, $4, 'ILS', 'captured', now(), $5)
         returning *`,
        [
          tenantId,
          chargeId,
          method,
          amount,
          JSON.stringify({ offline: true, recorded_by: actorUserId, notes }),
        ],
      );
      return rows[0]!;
    });
  }

  private async fetchCharge(tenantId: string, id: string): Promise<Charge> {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      const { rows } = await client.query<Charge>(`select * from charges where id = $1`, [id]);
      if (rows.length === 0) throw new NotFoundException('Charge not found');
      return rows[0]!;
    });
  }

  private async fetchPaymentMethod(tenantId: string, id: string) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      const { rows } = await client.query<PaymentMethod>(
        `select * from payment_methods where id = $1 and status = 'active'`,
        [id],
      );
      return rows[0] ?? null;
    });
  }

  private async fetchDefaultPaymentMethod(tenantId: string, personId: string) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      const { rows } = await client.query<PaymentMethod>(
        `select * from payment_methods
         where owner_person_id = $1 and status = 'active'
         order by is_default desc, created_at desc
         limit 1`,
        [personId],
      );
      return rows[0] ?? null;
    });
  }
}
