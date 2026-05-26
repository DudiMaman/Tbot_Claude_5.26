/**
 * DunningService — manages overdue charge escalation per SPEC §11.4.
 *
 * Default policy stages:
 *  T+0  fail  → retry 24h
 *  T+3  email reminder to billed_to_person
 *  T+7  SMS + WhatsApp
 *  T+14 push + WhatsApp + notify OWNER if billed_to_person != owner
 *  T+21 final notice + mgmt task
 *  T+30 legal_review flag + force-notify both bill_payer and owner
 *
 * Executed by a daily BullMQ job.
 */
import { Injectable, Logger } from '@nestjs/common';
import { DbService } from '../../db/db.service';
import { DUNNING_STAGES } from '@bm/shared/constants';

@Injectable()
export class DunningService {
  private readonly logger = new Logger(DunningService.name);

  constructor(private readonly db: DbService) {}

  /**
   * Iterate overdue charges per tenant and advance their dunning stage.
   * Should be called by a daily cron via BullMQ.
   */
  async runForTenant(tenantId: string, now: Date = new Date()) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      const { rows } = await client.query<{
        id: string;
        billed_to_person_id: string | null;
        apartment_id: string;
        due_date: string;
        dunning_stage: number;
      }>(
        `select id, billed_to_person_id, apartment_id, due_date, dunning_stage
         from charges
         where status in ('pending', 'partial', 'overdue')
           and due_date <= $1`,
        [now.toISOString().slice(0, 10)],
      );

      let advanced = 0;
      for (const row of rows) {
        const daysOverdue = Math.floor(
          (now.getTime() - new Date(row.due_date).getTime()) / (1000 * 60 * 60 * 24),
        );
        const nextStage = this.computeNextStage(row.dunning_stage, daysOverdue);
        if (nextStage > row.dunning_stage) {
          await client.query(
            `update charges
             set dunning_stage = $2, status = 'overdue', last_reminder_at = now()
             where id = $1`,
            [row.id, nextStage],
          );
          advanced++;
          // The actual notification dispatch is done by NotificationsModule
          // listening to a domain event we'd emit here. For brevity in this
          // skeleton, the dispatch hook is left to the queue worker.
        }
      }
      this.logger.log(`Dunning for ${tenantId}: ${advanced} charges advanced (of ${rows.length})`);
      return { reviewed: rows.length, advanced };
    });
  }

  private computeNextStage(current: number, daysOverdue: number): number {
    for (let i = DUNNING_STAGES.length - 1; i >= 0; i--) {
      const stage = DUNNING_STAGES[i]!;
      if (daysOverdue >= stage.day) {
        return Math.max(current, stage.stage);
      }
    }
    return current;
  }
}
