import { Body, Controller, Post, Req, UseGuards } from '@nestjs/common';
import { WhatsAppService } from './whatsapp.service';
import { SupabaseJwtGuard, type AuthenticatedRequest } from '../auth/supabase-jwt.guard';
import { Roles, RolesGuard } from '../auth/roles.decorator';

@Controller('whatsapp')
@UseGuards(SupabaseJwtGuard, RolesGuard)
@Roles('mgmt_admin', 'mgmt_member')
export class WhatsAppController {
  constructor(private readonly wa: WhatsAppService) {}

  @Post('send-text')
  sendText(@Req() _req: AuthenticatedRequest, @Body() body: { to: string; body: string }) {
    return this.wa.sendText(body.to, body.body);
  }

  @Post('send-template')
  sendTemplate(
    @Req() _req: AuthenticatedRequest,
    @Body() body: { to: string; template_key: string; vars: Record<string, string> },
  ) {
    return this.wa.sendTemplate(body.to, body.template_key, body.vars);
  }
}
