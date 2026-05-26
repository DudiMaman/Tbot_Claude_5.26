import { Injectable, Logger } from '@nestjs/common';
import axios from 'axios';
import { DbService } from '../../../db/db.service';

@Injectable()
export class InforuSmsSender {
  private readonly logger = new Logger(InforuSmsSender.name);
  constructor(private readonly db: DbService) {}

  async send(personId: string, body: string): Promise<string | undefined> {
    const { rows } = await this.db.query<{ phone_e164: string }>(
      `select phone_e164 from people where id = $1 and phone_e164 is not null`,
      [personId],
    );
    const phone = rows[0]?.phone_e164;
    if (!phone) return undefined;
    if (!process.env.INFORU_API_KEY) {
      this.logger.log(`[MOCK sms] to=${phone} body="${body.slice(0, 40)}..."`);
      return `mock_sms_${Date.now()}`;
    }
    const res = await axios.post(
      'https://capi.inforu.co.il/api/v2/SMS/SendSms',
      {
        Data: {
          Message: body,
          Recipients: [{ Phone: phone }],
          Settings: { Sender: process.env.INFORU_SENDER ?? 'BuildingMgmt' },
        },
      },
      {
        headers: { Authorization: `Basic ${Buffer.from(`${process.env.INFORU_USERNAME}:${process.env.INFORU_API_KEY}`).toString('base64')}` },
        timeout: 10_000,
      },
    );
    return res.data?.MessageId as string;
  }
}
