import { Module } from '@nestjs/common';
import { AiBotController } from './ai-bot.controller';
import { AiBotService } from './ai-bot.service';
import { ApartmentsModule } from '../apartments/apartments.module';
import { TicketsModule } from '../tickets/tickets.module';

@Module({
  imports: [ApartmentsModule, TicketsModule],
  controllers: [AiBotController],
  providers: [AiBotService],
  exports: [AiBotService],
})
export class AiBotModule {}
