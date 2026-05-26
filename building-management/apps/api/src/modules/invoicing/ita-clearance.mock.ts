import { Injectable, Logger } from '@nestjs/common';
import { ItaClearanceAdapter, type ItaClearanceInput, type ItaClearanceResult } from './ita-clearance.adapter';
import { ITA_E_INVOICE_THRESHOLD_ILS } from '@bm/shared/constants';

@Injectable()
export class ItaClearanceMockAdapter extends ItaClearanceAdapter {
  protected override readonly logger = new Logger(ItaClearanceMockAdapter.name);

  override async request(input: ItaClearanceInput): Promise<ItaClearanceResult> {
    if (input.invoice_total_ils < ITA_E_INVOICE_THRESHOLD_ILS) {
      return { required: false, status: 'not_required' };
    }
    const allocation = `MOCK-${Date.now().toString(36).toUpperCase()}`;
    this.logger.log(`[MOCK] ITA clearance approved: ${allocation}`);
    return { required: true, status: 'approved', allocation_number: allocation };
  }
}
