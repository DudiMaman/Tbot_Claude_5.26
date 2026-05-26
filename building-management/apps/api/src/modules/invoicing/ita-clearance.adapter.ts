/**
 * Israel Tax Authority (ITA) e-invoicing clearance adapter.
 *
 * Since 2024, invoices over a configurable threshold (currently ₪25k, dropping
 * to ₪10k by 2026) require obtaining a digital allocation number from the ITA
 * before issuance.
 *
 * Real implementation:
 *   - OAuth2 with ITA system using ITA_CLIENT_ID/SECRET
 *   - POST signed XML payload to ITA endpoint
 *   - Response: allocation_number (מספר הקצאה)
 *
 * Reference: https://www.gov.il/he/departments/general/tax-authority-invoice-allocation-numbers
 */
import { Injectable, Logger } from '@nestjs/common';
import axios from 'axios';
import { ITA_E_INVOICE_THRESHOLD_ILS } from '@bm/shared/constants';

export interface ItaClearanceInput {
  tenant_vat_id: string;
  customer_vat_id: string | null;
  invoice_type: 'tax_invoice' | 'tax_invoice_receipt' | 'credit_note';
  invoice_total_ils: number;
  invoice_date: string; // ISO date
}

export interface ItaClearanceResult {
  required: boolean;
  status: 'not_required' | 'approved' | 'rejected';
  allocation_number?: string;
  rejection_reason?: string;
  raw?: unknown;
}

@Injectable()
export class ItaClearanceAdapter {
  protected readonly logger = new Logger(ItaClearanceAdapter.name);
  protected readonly baseUrl = process.env.ITA_BASE_URL ?? '';
  protected readonly clientId = process.env.ITA_CLIENT_ID ?? '';
  protected readonly clientSecret = process.env.ITA_CLIENT_SECRET ?? '';
  private accessToken: { token: string; expiresAt: number } | null = null;

  async request(input: ItaClearanceInput): Promise<ItaClearanceResult> {
    if (input.invoice_total_ils < ITA_E_INVOICE_THRESHOLD_ILS) {
      return { required: false, status: 'not_required' };
    }
    if (!this.baseUrl || !this.clientId) {
      throw new Error('ITA not configured');
    }
    const token = await this.getAccessToken();
    try {
      const res = await axios.post(
        `${this.baseUrl}/api/invoice-allocation`,
        {
          tenant_vat_id: input.tenant_vat_id,
          customer_vat_id: input.customer_vat_id,
          invoice_type: input.invoice_type,
          total_ils: input.invoice_total_ils,
          invoice_date: input.invoice_date,
        },
        { headers: { Authorization: `Bearer ${token}` }, timeout: 30_000 },
      );
      return {
        required: true,
        status: 'approved',
        allocation_number: res.data.allocation_number,
        raw: res.data,
      };
    } catch (err) {
      this.logger.error(`ITA clearance failed: ${(err as Error).message}`);
      return {
        required: true,
        status: 'rejected',
        rejection_reason: (err as Error).message,
      };
    }
  }

  protected async getAccessToken(): Promise<string> {
    if (this.accessToken && this.accessToken.expiresAt > Date.now() + 60_000) {
      return this.accessToken.token;
    }
    const res = await axios.post(`${this.baseUrl}/oauth/token`, {
      client_id: this.clientId,
      client_secret: this.clientSecret,
      grant_type: 'client_credentials',
    });
    const { access_token, expires_in } = res.data;
    this.accessToken = { token: access_token, expiresAt: Date.now() + expires_in * 1000 };
    return access_token;
  }
}
