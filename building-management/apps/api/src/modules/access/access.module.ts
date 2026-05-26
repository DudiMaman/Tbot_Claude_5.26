import { Module } from '@nestjs/common';
import { AccessController } from './access.controller';
import { AccessService } from './access.service';
import { HttpWebhookProvider } from './providers/http-webhook.provider';
import { MockProvider } from './providers/mock.provider';

@Module({
  controllers: [AccessController],
  providers: [AccessService, HttpWebhookProvider, MockProvider],
  exports: [AccessService],
})
export class AccessModule {}
