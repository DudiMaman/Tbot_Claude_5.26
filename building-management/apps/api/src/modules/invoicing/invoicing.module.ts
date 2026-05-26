import { Module } from '@nestjs/common';
import { InvoicingController } from './invoicing.controller';
import { InvoicingService } from './invoicing.service';
import { ItaClearanceAdapter } from './ita-clearance.adapter';
import { ItaClearanceMockAdapter } from './ita-clearance.mock';

@Module({
  controllers: [InvoicingController],
  providers: [
    InvoicingService,
    {
      provide: ItaClearanceAdapter,
      useFactory: () => {
        if (process.env.ITA_MODE === 'mock' || !process.env.ITA_CLIENT_ID) {
          return new ItaClearanceMockAdapter();
        }
        return new ItaClearanceAdapter();
      },
    },
  ],
  exports: [InvoicingService],
})
export class InvoicingModule {}
