/**
 * WhatsAppService — Meta WhatsApp Business Cloud API integration.
 * See SPEC §13.
 */
import { Injectable, Logger } from '@nestjs/common';
import axios from 'axios';
import { DbService } from '../../db/db.service';
import { findTemplate } from '@bm/shared/templates';

@Injectable()
export class WhatsAppService {
  private readonly logger = new Logger(WhatsAppService.name);
  private readonly baseUrl = 'https://graph.facebook.com/v21.0';

  constructor(private readonly db: DbService) {}

  async sendText(toE164: string, body: string): Promise<string | undefined> {
    if (process.env.WHATSAPP_MODE === 'mock' || !process.env.WHATSAPP_PHONE_NUMBER_ID) {
      this.logger.log(`[MOCK whatsapp] to=${toE164} body="${body.slice(0, 40)}..."`);
      return `mock_wa_${Date.now()}`;
    }
    const res = await axios.post(
      `${this.baseUrl}/${process.env.WHATSAPP_PHONE_NUMBER_ID}/messages`,
      {
        messaging_product: 'whatsapp',
        to: toE164.replace('+', ''),
        type: 'text',
        text: { body },
      },
      {
        headers: { Authorization: `Bearer ${process.env.WHATSAPP_ACCESS_TOKEN}` },
        timeout: 15_000,
      },
    );
    return res.data?.messages?.[0]?.id as string;
  }

  async sendTemplate(toE164: string, templateKey: string, vars: Record<string, string>): Promise<string | undefined> {
    const tmpl = findTemplate(templateKey, 'whatsapp');
    if (!tmpl?.meta_template_name) {
      this.logger.warn(`Template not found or not configured: ${templateKey}`);
      return undefined;
    }
    if (process.env.WHATSAPP_MODE === 'mock') {
      this.logger.log(`[MOCK whatsapp template] to=${toE164} name=${tmpl.meta_template_name}`);
      return `mock_wat_${Date.now()}`;
    }
    const components = Object.values(vars).map((v) => ({ type: 'text', text: v }));
    const res = await axios.post(
      `${this.baseUrl}/${process.env.WHATSAPP_PHONE_NUMBER_ID}/messages`,
      {
        messaging_product: 'whatsapp',
        to: toE164.replace('+', ''),
        type: 'template',
        template: {
          name: tmpl.meta_template_name,
          language: { code: tmpl.meta_template_lang ?? 'he' },
          components: [{ type: 'body', parameters: components }],
        },
      },
      {
        headers: { Authorization: `Bearer ${process.env.WHATSAPP_ACCESS_TOKEN}` },
        timeout: 15_000,
      },
    );
    return res.data?.messages?.[0]?.id as string;
  }

  /** Process inbound webhook message: find conversation, append message. */
  async ingestInbound(payload: any) {
    const entry = payload?.entry?.[0];
    const change = entry?.changes?.[0];
    const value = change?.value;
    const phoneNumberId = value?.metadata?.phone_number_id;
    const messages = value?.messages ?? [];

    for (const m of messages) {
      const from = `+${m.from}`;
      const body: string | undefined = m.text?.body;
      const wamid = m.id;

      // Resolve tenant by phone_number_id (in production: lookup table)
      const tenantRes = await this.db.query<{ tenant_id: string }>(
        `select id as tenant_id from tenants where settings ->> 'whatsapp_phone_number_id' = $1 limit 1`,
        [phoneNumberId],
      );
      if (tenantRes.rows.length === 0) {
        this.logger.warn(`Unknown WA phone_number_id: ${phoneNumberId}`);
        continue;
      }
      const tenantId = tenantRes.rows[0]!.tenant_id;

      // Find or create person
      const personRes = await this.db.query<{ id: string }>(
        `select id from people where tenant_id = $1 and phone_e164 = $2 limit 1`,
        [tenantId, from],
      );
      let personId = personRes.rows[0]?.id;

      // Find/create conversation
      let convId: string;
      const convRes = await this.db.query<{ id: string }>(
        `select id from conversations
         where tenant_id = $1 and channel = 'whatsapp' and whatsapp_phone_e164 = $2
           and status <> 'closed' limit 1`,
        [tenantId, from],
      );
      if (convRes.rows.length > 0) {
        convId = convRes.rows[0]!.id;
      } else {
        const ins = await this.db.query<{ id: string }>(
          `insert into conversations (tenant_id, person_id, channel, status, whatsapp_phone_e164, last_message_at)
           values ($1, $2, 'whatsapp', 'pending_bot', $3, now()) returning id`,
          [tenantId, personId ?? null, from],
        );
        convId = ins.rows[0]!.id;
      }

      await this.db.query(
        `insert into messages (tenant_id, conversation_id, direction, sender_type, body, whatsapp_message_id, status, created_at)
         values ($1, $2, 'in', 'resident', $3, $4, 'delivered', now())
         on conflict do nothing`,
        [tenantId, convId, body ?? '', wamid],
      );
    }
  }

  verifyToken(query: { 'hub.mode'?: string; 'hub.challenge'?: string; 'hub.verify_token'?: string }) {
    if (query['hub.mode'] === 'subscribe' && query['hub.verify_token'] === process.env.WHATSAPP_WEBHOOK_VERIFY_TOKEN) {
      return query['hub.challenge'];
    }
    return null;
  }
}
