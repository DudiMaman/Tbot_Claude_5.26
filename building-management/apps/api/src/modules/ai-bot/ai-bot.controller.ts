import { Body, Controller, Param, Post, Req, UseGuards } from '@nestjs/common';
import { AiBotService } from './ai-bot.service';
import { SupabaseJwtGuard, type AuthenticatedRequest } from '../auth/supabase-jwt.guard';

@Controller('bot/conversations/:id')
@UseGuards(SupabaseJwtGuard)
export class AiBotController {
  constructor(private readonly bot: AiBotService) {}

  @Post('messages')
  send(
    @Req() req: AuthenticatedRequest,
    @Param('id') conversationId: string,
    @Body() body: { text: string },
  ) {
    return this.bot.respond(req.claims.tenant_id, conversationId, body.text);
  }
}
