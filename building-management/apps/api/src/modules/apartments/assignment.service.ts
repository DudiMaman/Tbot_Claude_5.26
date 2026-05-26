/**
 * AssignmentService — the heart of the owner/renter/bill-payer model.
 * See SPEC.md §3.6
 *
 * Implements the bill-payer resolution algorithm: given an apartment and a
 * schedule's rule, return the Person who should be billed.
 *
 * Used by BillingModule at cycle-generation time to materialize charges.
 */

import { Injectable, Logger } from '@nestjs/common';
import { DbService } from '../../db/db.service';
import type { BillPayerRule } from '@bm/db';

export interface ResolveBillPayerInput {
  tenantId: string;
  apartmentId: string;
  rule: BillPayerRule;
  specificPersonId?: string;
  asOfDate?: Date;
}

export interface ResolveBillPayerResult {
  apartment_id: string;
  resolved_person_id: string | null;
  rule_used: BillPayerRule;
  fallback_used: boolean;
  reason_no_payer?: string;
}

@Injectable()
export class AssignmentService {
  private readonly logger = new Logger(AssignmentService.name);

  constructor(private readonly db: DbService) {}

  /**
   * Resolve who should pay the va'ad fees for this apartment as of `asOfDate`.
   *
   * Algorithm (matches SPEC §3.6.4 exactly):
   *   1. If rule = specific_person_id    => return schedule.bill_payer_person_id
   *   2. If rule = owner                  => return primary owner
   *   3. If rule = primary_occupant       => return primary occupant
   *   4. If rule = current_bill_payer     => return assignment with is_bill_payer=true
   *      Fallback chain:
   *        a) primary owner
   *        b) any owner
   *        c) primary occupant
   *        d) flag as unbilled_no_payer
   */
  async resolveBillPayer(input: ResolveBillPayerInput): Promise<ResolveBillPayerResult> {
    const { tenantId, apartmentId, rule, specificPersonId } = input;
    const asOf = input.asOfDate ?? new Date();

    if (rule === 'specific_person_id') {
      return {
        apartment_id: apartmentId,
        resolved_person_id: specificPersonId ?? null,
        rule_used: rule,
        fallback_used: false,
        reason_no_payer: specificPersonId ? undefined : 'specific_person_id not set',
      };
    }

    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      const baseSql = `
        select aa.person_id, aa.role, aa.is_primary, aa.is_occupant, aa.is_bill_payer
        from apartment_assignments aa
        where aa.apartment_id = $1
          and aa.status = 'active'
          and aa.valid_from <= $2
          and (aa.valid_to is null or aa.valid_to >= $2)
      `;
      const params = [apartmentId, asOf.toISOString().slice(0, 10)];
      const { rows } = await client.query<{
        person_id: string;
        role: string;
        is_primary: boolean;
        is_occupant: boolean;
        is_bill_payer: boolean;
      }>(baseSql, params);

      const billPayer = rows.find((r) => r.is_bill_payer);
      const primaryOwner = rows.find((r) => r.role === 'owner' && r.is_primary);
      const anyOwner = rows.find((r) => r.role === 'owner');
      const primaryOccupant = rows.find((r) => r.is_occupant && r.is_primary);

      if (rule === 'owner') {
        const found = primaryOwner ?? anyOwner;
        return {
          apartment_id: apartmentId,
          resolved_person_id: found?.person_id ?? null,
          rule_used: rule,
          fallback_used: !primaryOwner && !!anyOwner,
          reason_no_payer: found ? undefined : 'no owner assignment',
        };
      }

      if (rule === 'primary_occupant') {
        return {
          apartment_id: apartmentId,
          resolved_person_id: primaryOccupant?.person_id ?? null,
          rule_used: rule,
          fallback_used: false,
          reason_no_payer: primaryOccupant ? undefined : 'no primary occupant',
        };
      }

      // rule = current_bill_payer
      if (billPayer) {
        return {
          apartment_id: apartmentId,
          resolved_person_id: billPayer.person_id,
          rule_used: rule,
          fallback_used: false,
        };
      }
      // Fallback chain
      const fallback = primaryOwner ?? anyOwner ?? primaryOccupant;
      if (fallback) {
        this.logger.debug(`Bill payer fallback for ${apartmentId}: ${fallback.person_id}`);
        return {
          apartment_id: apartmentId,
          resolved_person_id: fallback.person_id,
          rule_used: rule,
          fallback_used: true,
        };
      }
      return {
        apartment_id: apartmentId,
        resolved_person_id: null,
        rule_used: rule,
        fallback_used: false,
        reason_no_payer: 'apartment has no active assignment',
      };
    });
  }

  /** Get all current assignments for an apartment (with person details). */
  async listCurrent(tenantId: string, apartmentId: string) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      const { rows } = await client.query(
        `select aa.*, p.full_name, p.phone_e164, p.email
         from apartment_assignments aa
         join people p on p.id = aa.person_id
         where aa.apartment_id = $1
           and aa.status = 'active'
           and (aa.valid_to is null or aa.valid_to >= current_date)
         order by aa.role, aa.is_primary desc`,
        [apartmentId],
      );
      return rows;
    });
  }
}
