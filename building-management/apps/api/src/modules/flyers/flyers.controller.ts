import { Controller, Param, Post, Req, UseGuards } from '@nestjs/common';
import { FlyersService } from './flyers.service';
import { SupabaseJwtGuard, type AuthenticatedRequest } from '../auth/supabase-jwt.guard';
import { Roles, RolesGuard } from '../auth/roles.decorator';

@Controller('buildings/:id/flyer')
@UseGuards(SupabaseJwtGuard, RolesGuard)
@Roles('mgmt_admin', 'mgmt_member')
export class FlyersController {
  constructor(private readonly flyers: FlyersService) {}

  @Post()
  generate(@Req() req: AuthenticatedRequest, @Param('id') id: string) {
    return this.flyers.generate(req.claims.tenant_id, id);
  }
}
