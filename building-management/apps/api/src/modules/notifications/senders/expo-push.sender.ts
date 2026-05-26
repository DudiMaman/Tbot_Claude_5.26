import { Injectable, Logger } from '@nestjs/common';
import axios from 'axios';
import { DbService } from '../../../db/db.service';

@Injectable()
export class ExpoPushSender {
  private readonly logger = new Logger(ExpoPushSender.name);
  constructor(private readonly db: DbService) {}

  async send(personId: string, title: string, body: string): Promise<string | undefined> {
    const { rows } = await this.db.query<{ push_token: string }>(
      `select push_token from people where id = $1 and push_token is not null`,
      [personId],
    );
    const token = rows[0]?.push_token;
    if (!token) return undefined;
    if (!process.env.EXPO_ACCESS_TOKEN) {
      this.logger.log(`[MOCK push] to=${personId} title="${title}"`);
      return `mock_${Date.now()}`;
    }
    const res = await axios.post(
      'https://exp.host/--/api/v2/push/send',
      { to: token, title, body },
      { headers: { Authorization: `Bearer ${process.env.EXPO_ACCESS_TOKEN}` }, timeout: 10_000 },
    );
    return (res.data?.data?.id as string) ?? undefined;
  }
}
