import { Injectable, Logger } from '@nestjs/common';
import axios from 'axios';
import { DbService } from '../../../db/db.service';

@Injectable()
export class ResendEmailSender {
  private readonly logger = new Logger(ResendEmailSender.name);
  constructor(private readonly db: DbService) {}

  async send(personId: string, subject: string, body: string): Promise<string | undefined> {
    const { rows } = await this.db.query<{ email: string }>(
      `select email from people where id = $1 and email is not null`,
      [personId],
    );
    const to = rows[0]?.email;
    if (!to) return undefined;
    if (!process.env.RESEND_API_KEY) {
      this.logger.log(`[MOCK email] to=${to} subject="${subject}"`);
      return `mock_email_${Date.now()}`;
    }
    const res = await axios.post(
      'https://api.resend.com/emails',
      {
        from: process.env.RESEND_FROM ?? 'no-reply@example.com',
        to,
        subject,
        text: body,
      },
      { headers: { Authorization: `Bearer ${process.env.RESEND_API_KEY}` }, timeout: 10_000 },
    );
    return res.data?.id as string;
  }
}
