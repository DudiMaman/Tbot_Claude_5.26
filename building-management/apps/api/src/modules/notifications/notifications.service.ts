/**
 * NotificationsService — central fanout across channels.
 * See SPEC §21.
 */
import { Injectable, Logger } from '@nestjs/common';
import { DbService } from '../../db/db.service';
import { ExpoPushSender } from './senders/expo-push.sender';
import { ResendEmailSender } from './senders/resend-email.sender';
import { InforuSmsSender } from './senders/inforu-sms.sender';
import { findTemplate, renderTemplate } from '@bm/shared/templates';
import { NOTIFICATION_DND_HOURS } from '@bm/shared/constants';
import type { NotificationChannel } from '@bm/db';

export interface SendInput {
  tenant_id: string;
  recipient_person_id?: string;
  recipient_user_id?: string;
  channel: NotificationChannel;
  template_key: string;
  vars: Record<string, string | number>;
  dedupe_key?: string;
  bypass_dnd?: boolean;
}

@Injectable()
export class NotificationsService {
  private readonly logger = new Logger(NotificationsService.name);

  constructor(
    private readonly db: DbService,
    private readonly push: ExpoPushSender,
    private readonly email: ResendEmailSender,
    private readonly sms: InforuSmsSender,
  ) {}

  async send(input: SendInput) {
    // DND check
    if (!input.bypass_dnd && this.inDnd()) {
      this.logger.debug(`Notification skipped due to DND: ${input.template_key}`);
      return { ok: false, reason: 'dnd' };
    }

    // Dedupe
    if (input.dedupe_key) {
      const existing = await this.db.query(
        `select 1 from notifications where tenant_id = $1 and dedupe_key = $2 limit 1`,
        [input.tenant_id, input.dedupe_key],
      );
      if (existing.rows.length > 0) return { ok: false, reason: 'duplicate' };
    }

    const template = findTemplate(input.template_key, input.channel);
    if (!template) {
      this.logger.warn(`Template not found: ${input.template_key}/${input.channel}`);
      return { ok: false, reason: 'no_template' };
    }
    const body = renderTemplate(template.body, input.vars);
    const subject = template.subject ? renderTemplate(template.subject, input.vars) : undefined;

    // Persist
    const { rows } = await this.db.query(
      `insert into notifications
        (tenant_id, recipient_person_id, recipient_user_id, channel, template_key, payload, dedupe_key, status)
       values ($1, $2, $3, $4, $5, $6, $7, 'queued') returning id`,
      [
        input.tenant_id,
        input.recipient_person_id ?? null,
        input.recipient_user_id ?? null,
        input.channel,
        input.template_key,
        JSON.stringify({ vars: input.vars, body, subject }),
        input.dedupe_key ?? null,
      ],
    );
    const notifId = (rows[0] as any).id as string;

    // Dispatch
    try {
      let providerMessageId: string | undefined;
      if (input.channel === 'push' && input.recipient_person_id) {
        providerMessageId = await this.push.send(input.recipient_person_id, subject ?? '', body);
      } else if (input.channel === 'email' && input.recipient_person_id) {
        providerMessageId = await this.email.send(input.recipient_person_id, subject ?? '', body);
      } else if (input.channel === 'sms' && input.recipient_person_id) {
        providerMessageId = await this.sms.send(input.recipient_person_id, body);
      }
      await this.db.query(
        `update notifications set status = 'sent', sent_at = now(), provider_message_id = $2 where id = $1`,
        [notifId, providerMessageId ?? null],
      );
      return { ok: true, id: notifId };
    } catch (err) {
      this.logger.warn(`Notification send failed: ${(err as Error).message}`);
      await this.db.query(`update notifications set status = 'failed' where id = $1`, [notifId]);
      return { ok: false, reason: (err as Error).message };
    }
  }

  private inDnd(now: Date = new Date()): boolean {
    const hour = now.getUTCHours() + 3; // Israel offset; in production use date-fns-tz
    const h = (hour + 24) % 24;
    if (NOTIFICATION_DND_HOURS.start > NOTIFICATION_DND_HOURS.end) {
      return h >= NOTIFICATION_DND_HOURS.start || h < NOTIFICATION_DND_HOURS.end;
    }
    return h >= NOTIFICATION_DND_HOURS.start && h < NOTIFICATION_DND_HOURS.end;
  }
}
