import { Body, Controller, Get, Logger, Post, Query, Res } from '@nestjs/common';
import type { Response } from 'express';
import { Public } from '../auth/public.decorator';
import { WhatsAppService } from './whatsapp.service';

@Controller('webhooks/whatsapp')
export class WhatsAppWebhookController {
  private readonly logger = new Logger(WhatsAppWebhookController.name);

  constructor(private readonly wa: WhatsAppService) {}

  @Public()
  @Get()
  verify(
    @Query() query: { 'hub.mode'?: string; 'hub.challenge'?: string; 'hub.verify_token'?: string },
    @Res() res: Response,
  ) {
    const challenge = this.wa.verifyToken(query);
    if (challenge) return res.status(200).send(challenge);
    return res.status(403).send('forbidden');
  }

  @Public()
  @Post()
  async receive(@Body() payload: unknown) {
    try {
      await this.wa.ingestInbound(payload);
    } catch (err) {
      this.logger.error(`Webhook ingest failed: ${(err as Error).message}`);
    }
    return { ok: true };
  }
}
