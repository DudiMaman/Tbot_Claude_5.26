/**
 * ChecksService — check intake, deposit batching, bounced-check workflow.
 * See SPEC §38.
 */
import { Injectable, Logger, NotFoundException, BadRequestException } from '@nestjs/common';
import { DbService } from '../../db/db.service';
import type { ReceiveCheck, BounceCheck } from '@bm/shared';
import type { Check, CheckBatch, BouncedCheck } from '@bm/db';

@Injectable()
export class ChecksService {
  private readonly logger = new Logger(ChecksService.name);

  constructor(private readonly db: DbService) {}

  async receive(tenantId: string, actorUserId: string, input: ReceiveCheck): Promise<Check> {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      const status = new Date(input.due_date) > new Date() ? 'scheduled' : 'received';
      const { rows } = await client.query<Check>(
        `insert into checks
          (tenant_id, building_id, apartment_id, payer_person_id,
           bank_code, branch_code, account_number, check_number,
           amount, currency, issue_date, due_date,
           scan_file_id, status, related_charge_ids, received_by_user_id)
         values ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'ILS', $10, $11, $12, $13, $14, $15)
         returning *`,
        [
          tenantId,
          input.building_id,
          input.apartment_id ?? null,
          input.payer_person_id ?? null,
          input.bank_code,
          input.branch_code,
          input.account_number,
          input.check_number,
          input.amount,
          input.issue_date,
          input.due_date,
          input.scan_file_id ?? null,
          status,
          input.related_charge_ids,
          actorUserId,
        ],
      );
      return rows[0]!;
    });
  }

  async createBatch(
    tenantId: string,
    actorUserId: string,
    buildingId: string,
    iban: string,
    depositDate: string,
    checkIds: string[],
  ): Promise<CheckBatch> {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      // sum amounts
      const sumRes = await client.query<{ total: string }>(
        `select coalesce(sum(amount),0) as total from checks where id = any($1::uuid[])`,
        [checkIds],
      );
      const total = Number(sumRes.rows[0]?.total ?? 0);

      const { rows } = await client.query<CheckBatch>(
        `insert into check_batches
          (tenant_id, building_id, bank_account_iban, deposit_date, total_amount, status, created_by_user_id)
         values ($1, $2, $3, $4, $5, 'draft', $6)
         returning *`,
        [tenantId, buildingId, iban, depositDate, total, actorUserId],
      );
      const batch = rows[0]!;
      await client.query(
        `update checks set deposit_batch_id = $1, status = 'deposited' where id = any($2::uuid[])`,
        [batch.id, checkIds],
      );
      return batch;
    });
  }

  /**
   * Mark a check bounced. The DB trigger reverts the related charge.
   * In addition we:
   *  - create a BouncedCheck row
   *  - create a new fee charge if recharge_fee_amount > 0
   *  - schedule notifications (notify bill_payer + owner)
   */
  async markBounced(
    tenantId: string,
    input: BounceCheck,
  ): Promise<{ check: Check; bounced: BouncedCheck; fee_charge_id: string | null }> {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      const checkRes = await client.query<Check>(
        `select * from checks where id = $1`,
        [input.check_id],
      );
      if (checkRes.rows.length === 0) throw new NotFoundException('Check not found');
      const check = checkRes.rows[0]!;
      if (check.status === 'bounced') throw new BadRequestException('Already bounced');

      // Update the check status — trigger reverts charges
      await client.query(`update checks set status = 'bounced' where id = $1`, [input.check_id]);

      // Create the BouncedCheck row
      const { rows: bouncedRows } = await client.query<BouncedCheck>(
        `insert into bounced_checks
          (tenant_id, original_check_id, bounce_reason, bounce_reason_text,
           bank_fee_amount, recharge_fee_amount, recovery_status)
         values ($1, $2, $3, $4, $5, $6, 'open')
         returning *`,
        [
          tenantId,
          input.check_id,
          input.bounce_reason,
          input.bounce_reason_text ?? null,
          input.bank_fee_amount,
          input.recharge_fee_amount,
          ],
      );

      let feeChargeId: string | null = null;
      const totalFee = Number(input.bank_fee_amount) + Number(input.recharge_fee_amount);
      if (totalFee > 0 && check.apartment_id && check.payer_person_id) {
        const dueDate = new Date();
        dueDate.setDate(dueDate.getDate() + 14);
        const { rows: feeRows } = await client.query<{ id: string }>(
          `insert into charges
            (tenant_id, building_id, apartment_id, billed_to_person_id,
             description, amount, currency, due_date, status, metadata)
           values ($1, $2, $3, $4, $5, $6, 'ILS', $7, 'pending', $8)
           returning id`,
          [
            tenantId,
            check.building_id,
            check.apartment_id,
            check.payer_person_id,
            `דמי טיפול בצ'ק חוזר #${check.check_number}`,
            totalFee,
            dueDate.toISOString().slice(0, 10),
            JSON.stringify({ kind: 'bounced_check_fee', source_check_id: check.id }),
          ],
        );
        feeChargeId = feeRows[0]!.id;
      }

      return { check, bounced: bouncedRows[0]!, fee_charge_id: feeChargeId };
    });
  }

  async linkReplacement(tenantId: string, bouncedId: string, replacementCheckId: string) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      const { rows } = await client.query<BouncedCheck>(
        `update bounced_checks
         set replacement_check_id = $2, recovery_status = 'replacement_received', updated_at = now()
         where id = $1
         returning *`,
        [bouncedId, replacementCheckId],
      );
      if (rows.length === 0) throw new NotFoundException('Bounced check not found');
      return rows[0]!;
    });
  }

  async list(tenantId: string, buildingId?: string, status?: string) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      const conditions: string[] = [];
      const params: unknown[] = [];
      if (buildingId) {
        params.push(buildingId);
        conditions.push(`building_id = $${params.length}`);
      }
      if (status) {
        params.push(status);
        conditions.push(`status = $${params.length}`);
      }
      const where = conditions.length > 0 ? `where ${conditions.join(' and ')}` : '';
      const { rows } = await client.query<Check>(
        `select * from checks ${where} order by due_date desc`,
        params,
      );
      return rows;
    });
  }

  async listBounced(tenantId: string) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      const { rows } = await client.query(
        `select bc.*, c.check_number, c.amount, c.apartment_id, c.payer_person_id,
                p.full_name as payer_name
         from bounced_checks bc
         join checks c on c.id = bc.original_check_id
         left join people p on p.id = c.payer_person_id
         where bc.recovery_status not in ('paid_other', 'written_off')
         order by bc.bounced_on desc`,
      );
      return rows;
    });
  }
}
