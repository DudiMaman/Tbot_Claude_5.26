import { Body, Controller, Headers, Logger, Post, RawBodyRequest, Req } from '@nestjs/common';
import { TranzilaAdapter } from './tranzila.adapter';
import { Public } from '../auth/public.decorator';
import { DbService } from '../../db/db.service';

/**
 * Tranzila notify webhook. Tranzila sends a POST with form-encoded body
 * containing transaction details. Idempotency via tranzila_txn_id.
 */
@Controller('webhooks/tranzila')
export class TranzilaWebhookController {
  private readonly logger = new Logger(TranzilaWebhookController.name);

  constructor(
    private readonly tranzila: TranzilaAdapter,
    private readonly db: DbService,
  ) {}

  @Public()
  @Post()
  async receive(
    @Req() req: RawBodyRequest<Request>,
    @Headers('x-tranzila-signature') signature: string,
    @Body() body: Record<string, string>,
  ) {
    const rawBody = (req.rawBody as Buffer | undefined)?.toString('utf-8') ?? JSON.stringify(body);
    if (signature && !this.tranzila.verifyWebhookSignature(rawBody, signature)) {
      this.logger.warn('Tranzila webhook signature mismatch — rejecting');
      return { ok: false };
    }

    const txnId = body.index ?? body.txn_id;
    const status = body.Response === '000' ? 'captured' : 'failed';
    if (!txnId) {
      this.logger.warn('Tranzila webhook missing txn id');
      return { ok: false };
    }

    await this.db.query(
      `update payments set status = $2, captured_at = case when $2 = 'captured' then now() else captured_at end,
                            raw_provider_json = $3
       where tranzila_txn_id = $1`,
      [txnId, status, JSON.stringify(body)],
    );
    return { ok: true };
  }
}
