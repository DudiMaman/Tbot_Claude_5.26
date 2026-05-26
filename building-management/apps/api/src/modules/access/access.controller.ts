import { Body, Controller, ForbiddenException, Get, Param, Post, Query, Req, UseGuards } from '@nestjs/common';
import { AccessService } from './access.service';
import { SupabaseJwtGuard, type AuthenticatedRequest } from '../auth/supabase-jwt.guard';

@Controller()
@UseGuards(SupabaseJwtGuard)
export class AccessController {
  constructor(private readonly access: AccessService) {}

  @Post('gates/:id/open')
  open(@Req() req: AuthenticatedRequest, @Param('id') id: string) {
    if (!req.claims.person_id) throw new ForbiddenException();
    return this.access.openAsPerson(req.claims.tenant_id, req.claims.person_id, id);
  }

  @Post('gates/:id/open-guest')
  openGuest(
    @Req() req: AuthenticatedRequest,
    @Param('id') id: string,
    @Body() body: { code: string },
  ) {
    return this.access.openAsGuest(req.claims.tenant_id, body.code, id);
  }

  @Post('guest-codes')
  createCode(
    @Req() req: AuthenticatedRequest,
    @Body() body: { building_id: string; gate_id?: string; valid_hours?: number; max_uses?: number },
  ) {
    if (!req.claims.person_id) throw new ForbiddenException();
    return this.access.createGuestCode(
      req.claims.tenant_id,
      req.claims.person_id,
      body.building_id,
      body.gate_id ?? null,
      body.valid_hours,
      body.max_uses,
    );
  }

  @Get('gates')
  list(@Req() req: AuthenticatedRequest, @Query('building_id') buildingId?: string) {
    return this.access.listGates(req.claims.tenant_id, buildingId);
  }
}
