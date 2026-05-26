import { Module } from '@nestjs/common';
import { BillingController } from './billing.controller';
import { BillingService } from './billing.service';
import { DunningService } from './dunning.service';
import { ApartmentsModule } from '../apartments/apartments.module';

@Module({
  imports: [ApartmentsModule],
  controllers: [BillingController],
  providers: [BillingService, DunningService],
  exports: [BillingService, DunningService],
})
export class BillingModule {}
