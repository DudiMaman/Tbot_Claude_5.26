import { Injectable, Logger } from '@nestjs/common';
import axios from 'axios';
import { createHmac } from 'node:crypto';
import type { AccessGate } from '@bm/db';

@Injectable()
export class HttpWebhookProvider {
  private readonly logger = new Logger(HttpWebhookProvider.name);

  async open(gate: AccessGate): Promise<{ ok: boolean; reason?: string }> {
    const config = gate.config as { url?: string; secret?: string; method?: 'GET' | 'POST' };
    if (!config.url) return { ok: false, reason: 'gate not configured' };

    const body = JSON.stringify({ gate_id: gate.id, ts: Date.now() });
    const signature = config.secret
      ? createHmac('sha256', config.secret).update(body).digest('hex')
      : undefined;

    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (signature) headers['X-Signature-SHA256'] = signature;
      const res =
        config.method === 'GET'
          ? await axios.get(config.url, { headers, timeout: 3000 })
          : await axios.post(config.url, body, { headers, timeout: 3000 });
      return { ok: res.status >= 200 && res.status < 300 };
    } catch (err) {
      this.logger.warn(`HttpWebhook open failed: ${(err as Error).message}`);
      return { ok: false, reason: (err as Error).message };
    }
  }
}
