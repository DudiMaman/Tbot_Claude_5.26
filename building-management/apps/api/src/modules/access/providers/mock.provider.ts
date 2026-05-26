import { Injectable, Logger } from '@nestjs/common';
import type { AccessGate } from '@bm/db';

@Injectable()
export class MockProvider {
  private readonly logger = new Logger(MockProvider.name);

  async open(gate: AccessGate): Promise<{ ok: boolean; reason?: string }> {
    this.logger.log(`[MOCK gate ${gate.name}] open`);
    await new Promise((r) => setTimeout(r, 200));
    return { ok: true };
  }
}
