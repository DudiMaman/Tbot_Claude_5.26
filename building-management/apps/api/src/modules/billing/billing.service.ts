/**
 * BillingService — cycle generation, dry-run, schedule CRUD.
 * See SPEC.md §11
 */
import { Injectable, Logger, NotFoundException } from '@nestjs/common';
import { DbService } from '../../db/db.service';
import { AssignmentService } from '../apartments/assignment.service';
import type { CreateChargeSchedule } from '@bm/shared';
import type { ChargeSchedule, BillPayerRule } from '@bm/db';
import type { DryRunCycle } from '@bm/types';

@Injectable()
export class BillingService {
  private readonly logger = new Logger(BillingService.name);

  constructor(
    private readonly db: DbService,
    private readonly assignments: AssignmentService,
  ) {}

  async createSchedule(tenantId: string, input: CreateChargeSchedule): Promise<ChargeSchedule> {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      const { rows } = await client.query<ChargeSchedule>(
        `insert into charge_schedules
          (tenant_id, building_id, apartment_id, name, description, amount, currency,
           cadence, day_of_month, start_date, end_date, installments_allowed,
           bill_payer_rule, bill_payer_person_id, status)
         values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, 'active')
         returning *`,
        [
          tenantId,
          input.building_id,
          input.apartment_id ?? null,
          input.name,
          input.description ?? null,
          input.amount,
          input.currency,
          input.cadence,
          input.day_of_month ?? null,
          input.start_date,
          input.end_date ?? null,
          input.installments_allowed,
          input.bill_payer_rule,
          input.bill_payer_person_id ?? null,
        ],
      );
      return rows[0]!;
    });
  }

  async listSchedules(tenantId: string, buildingId?: string) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      const { rows } = buildingId
        ? await client.query(
            `select * from charge_schedules where building_id = $1 and status <> 'ended' order by created_at desc`,
            [buildingId],
          )
        : await client.query(
            `select * from charge_schedules where status <> 'ended' order by created_at desc`,
          );
      return rows;
    });
  }

  /**
   * Dry-run a billing cycle for a schedule on a given date.
   * Returns the rows that would be created, with resolved bill payer info,
   * WITHOUT writing anything.
   */
  async dryRun(tenantId: string, scheduleId: string, asOfDate: Date): Promise<DryRunCycle> {
    const schedule = await this.fetchSchedule(tenantId, scheduleId);
    const apartments = await this.fetchApartmentsForSchedule(tenantId, schedule);
    const charges: DryRunCycle['charges'] = [];
    let unresolved = 0;
    let totalAmount = 0;

    for (const apt of apartments) {
      const resolved = await this.assignments.resolveBillPayer({
        tenantId,
        apartmentId: apt.id,
        rule: schedule.bill_payer_rule as BillPayerRule,
        specificPersonId: schedule.bill_payer_person_id ?? undefined,
        asOfDate,
      });
      if (resolved.resolved_person_id === null) unresolved++;
      const person = resolved.resolved_person_id
        ? await this.fetchPerson(tenantId, resolved.resolved_person_id)
        : null;
      const amount = Number(schedule.amount);
      totalAmount += amount;
      charges.push({
        apartment_id: apt.id,
        apartment_unit_number: apt.unit_number,
        billed_to_person_id: resolved.resolved_person_id,
        billed_to_name: person?.full_name ?? null,
        amount,
        status: resolved.resolved_person_id ? 'will_be_billed' : 'unresolved_payer',
      });
    }

    return {
      schedule_id: scheduleId,
      cycle_date: asOfDate.toISOString().slice(0, 10),
      charges,
      totals: { count: charges.length, unresolved, amount: totalAmount },
    };
  }

  /**
   * Run a real billing cycle: insert charges into the DB based on the schedule.
   * Idempotent on (schedule_id, apartment_id, due_date).
   */
  async runCycle(tenantId: string, scheduleId: string, dueDate: Date) {
    const schedule = await this.fetchSchedule(tenantId, scheduleId);
    const apartments = await this.fetchApartmentsForSchedule(tenantId, schedule);
    const dueIso = dueDate.toISOString().slice(0, 10);
    const created: string[] = [];

    for (const apt of apartments) {
      const resolved = await this.assignments.resolveBillPayer({
        tenantId,
        apartmentId: apt.id,
        rule: schedule.bill_payer_rule as BillPayerRule,
        specificPersonId: schedule.bill_payer_person_id ?? undefined,
        asOfDate: dueDate,
      });
      const status = resolved.resolved_person_id ? 'pending' : 'unbilled_no_payer';

      await this.db.withTenantContext(
        { tenant_id: tenantId, role: 'mgmt_admin' },
        async (client) => {
          // Idempotency check
          const exists = await client.query(
            `select id from charges
             where schedule_id = $1 and apartment_id = $2 and due_date = $3`,
            [scheduleId, apt.id, dueIso],
          );
          if (exists.rows.length > 0) return;

          const { rows } = await client.query<{ id: string }>(
            `insert into charges
              (tenant_id, building_id, apartment_id, billed_to_person_id, schedule_id,
               description, amount, currency, due_date, status)
             values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
             returning id`,
            [
              tenantId,
              schedule.building_id,
              apt.id,
              resolved.resolved_person_id,
              scheduleId,
              schedule.name,
              schedule.amount,
              schedule.currency,
              dueIso,
              status,
            ],
          );
          created.push(rows[0]!.id);
        },
      );
    }
    this.logger.log(`Cycle for schedule ${scheduleId} created ${created.length} charges`);
    return { created_charge_ids: created, total: created.length };
  }

  private async fetchSchedule(tenantId: string, scheduleId: string): Promise<ChargeSchedule> {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      const { rows } = await client.query<ChargeSchedule>(
        `select * from charge_schedules where id = $1`,
        [scheduleId],
      );
      if (rows.length === 0) throw new NotFoundException('Schedule not found');
      return rows[0]!;
    });
  }

  private async fetchApartmentsForSchedule(tenantId: string, schedule: ChargeSchedule) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      if (schedule.apartment_id) {
        const { rows } = await client.query<{ id: string; unit_number: string }>(
          `select id, unit_number from apartments where id = $1`,
          [schedule.apartment_id],
        );
        return rows;
      }
      const { rows } = await client.query<{ id: string; unit_number: string }>(
        `select id, unit_number from apartments
         where building_id = $1 and deleted_at is null
         order by unit_number`,
        [schedule.building_id],
      );
      return rows;
    });
  }

  private async fetchPerson(tenantId: string, personId: string) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      const { rows } = await client.query<{ id: string; full_name: string }>(
        `select id, full_name from people where id = $1`,
        [personId],
      );
      return rows[0] ?? null;
    });
  }
}
