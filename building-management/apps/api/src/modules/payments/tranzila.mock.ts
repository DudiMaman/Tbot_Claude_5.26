import { Injectable, Logger } from '@nestjs/common';
import { TranzilaAdapter, type ChargeTokenInput, type ChargeTokenResult } from './tranzila.adapter';

/**
 * In-memory Tranzila for local dev & tests.
 *  - Tokens that start with "fail_" always fail.
 *  - All others succeed and produce a fake txnId.
 */
@Injectable()
export class TranzilaMockAdapter extends TranzilaAdapter {
  protected override readonly logger = new Logger(TranzilaMockAdapter.name);

  override async chargeToken(input: ChargeTokenInput): Promise<ChargeTokenResult> {
    if (input.token.startsWith('fail_')) {
      return {
        ok: false,
        failureReason: 'mock: card declined',
        raw: { mock: true, response: '003' },
      };
    }
    const txnId = `mock_${input.idempotencyKey}_${Date.now()}`;
    this.logger.log(`[MOCK] chargeToken token=${input.token} amount=${input.amountIls} -> ${txnId}`);
    return {
      ok: true,
      txnId,
      raw: { mock: true, response: '000', sum: input.amountIls, installments: input.installments },
    };
  }

  override async refund(originalTxnId: string, amountIls: number): Promise<ChargeTokenResult> {
    return {
      ok: true,
      txnId: `mock_refund_${originalTxnId}_${Date.now()}`,
      raw: { mock: true, original: originalTxnId, amount: amountIls },
    };
  }

  override verifyWebhookSignature(): boolean {
    return true;
  }
}
