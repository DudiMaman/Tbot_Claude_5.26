/**
 * TranzilaAdapter — wraps the Tranzila REST API.
 *
 * Real implementation uses the Iframe Hosted Fields flow (PCI SAQ-A):
 *   1. Frontend embeds Tranzila iframe; user enters card.
 *   2. Tranzila returns a token (TranzilaTK) via postMessage.
 *   3. Token is sent to our backend and stored on payment_methods.
 *   4. Charge against the token via this adapter:
 *        POST https://secure5.tranzila.com/cgi-bin/tranzila71u.cgi
 *        body params: supplier, TranzilaTK, sum, currency=1 (ILS),
 *                     tranmode=V (immediate capture), npay (installments)
 *
 * Webhook signature verification uses HMAC-SHA256 of body with the
 * tenant-specific TRANZILA_HMAC_SECRET.
 */
import { Injectable, Logger } from '@nestjs/common';
import axios from 'axios';
import { createHmac, timingSafeEqual } from 'node:crypto';

export interface ChargeTokenInput {
  token: string;
  amountIls: number;
  currency: 'ILS';
  installments: number;
  description?: string;
  idempotencyKey: string;
}

export interface ChargeTokenResult {
  ok: boolean;
  txnId?: string;
  failureReason?: string;
  raw: unknown;
}

@Injectable()
export class TranzilaAdapter {
  protected readonly logger = new Logger(TranzilaAdapter.name);
  protected readonly baseUrl = process.env.TRANZILA_BASE_URL ?? 'https://secure5.tranzila.com';
  protected readonly supplier = process.env.TRANZILA_SUPPLIER ?? '';
  protected readonly hmacSecret = process.env.TRANZILA_HMAC_SECRET ?? '';

  async chargeToken(input: ChargeTokenInput): Promise<ChargeTokenResult> {
    if (!this.supplier) {
      throw new Error('TRANZILA_SUPPLIER not configured');
    }
    const params = new URLSearchParams({
      supplier: this.supplier,
      TranzilaTK: input.token,
      sum: input.amountIls.toFixed(2),
      currency: '1',
      tranmode: 'V',
      npay: String(input.installments),
      txnref: input.idempotencyKey,
    });
    if (input.description) params.set('Description', input.description);

    try {
      const res = await axios.post(
        `${this.baseUrl}/cgi-bin/tranzila71u.cgi`,
        params.toString(),
        {
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          timeout: 30_000,
        },
      );
      const parsed = new URLSearchParams(typeof res.data === 'string' ? res.data : '');
      const responseCode = parsed.get('Response');
      const index = parsed.get('index');
      if (responseCode === '000' && index) {
        return { ok: true, txnId: index, raw: Object.fromEntries(parsed) };
      }
      return {
        ok: false,
        failureReason: `Tranzila response ${responseCode}`,
        raw: Object.fromEntries(parsed),
      };
    } catch (err) {
      this.logger.error(`Tranzila chargeToken failed: ${(err as Error).message}`);
      return { ok: false, failureReason: (err as Error).message, raw: null };
    }
  }

  async refund(originalTxnId: string, amountIls: number): Promise<ChargeTokenResult> {
    const params = new URLSearchParams({
      supplier: this.supplier,
      sum: amountIls.toFixed(2),
      currency: '1',
      tranmode: 'R',
      indexRef: originalTxnId,
    });
    try {
      const res = await axios.post(
        `${this.baseUrl}/cgi-bin/tranzila71u.cgi`,
        params.toString(),
        { headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, timeout: 30_000 },
      );
      const parsed = new URLSearchParams(typeof res.data === 'string' ? res.data : '');
      return {
        ok: parsed.get('Response') === '000',
        txnId: parsed.get('index') ?? undefined,
        raw: Object.fromEntries(parsed),
      };
    } catch (err) {
      return { ok: false, failureReason: (err as Error).message, raw: null };
    }
  }

  verifyWebhookSignature(rawBody: string, signature: string): boolean {
    if (!this.hmacSecret) {
      this.logger.warn('No TRANZILA_HMAC_SECRET — webhook signature unverified');
      return true;
    }
    const expected = createHmac('sha256', this.hmacSecret).update(rawBody).digest('hex');
    const aBuf = Buffer.from(expected);
    const bBuf = Buffer.from(signature.replace(/^sha256=/, ''));
    if (aBuf.length !== bBuf.length) return false;
    return timingSafeEqual(aBuf, bBuf);
  }
}
