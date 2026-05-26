import { Module } from '@nestjs/common';
import { WhatsAppController } from './whatsapp.controller';
import { WhatsAppWebhookController } from './whatsapp.webhook';
import { WhatsAppService } from './whatsapp.service';
import { AiBotModule } from '../ai-bot/ai-bot.module';

@Module({
  imports: [AiBotModule],
  controllers: [WhatsAppController, WhatsAppWebhookController],
  providers: [WhatsAppService],
  exports: [WhatsAppService],
})
export class WhatsAppModule {}
