import { Body, Controller, ForbiddenException, Get, Param, Post, Query, Req, UseGuards } from '@nestjs/common';
import { BulletinService } from './bulletin.service';
import { SupabaseJwtGuard, type AuthenticatedRequest } from '../auth/supabase-jwt.guard';
import { CreateBulletinSchema } from '@bm/shared';
import { ZodPipe } from '../../common/zod.pipe';

@Controller('bulletin')
@UseGuards(SupabaseJwtGuard)
export class BulletinController {
  constructor(private readonly bulletin: BulletinService) {}

  @Post()
  create(@Req() req: AuthenticatedRequest, @Body(new ZodPipe(CreateBulletinSchema)) body: any) {
    if (req.claims.role === 'resident') throw new ForbiddenException();
    return this.bulletin.create(req.claims.tenant_id, req.claims.sub, body);
  }

  @Get()
  list(@Req() req: AuthenticatedRequest, @Query('building_id') buildingId: string) {
    return this.bulletin.listForBuilding(req.claims.tenant_id, buildingId);
  }

  @Post(':id/reactions')
  react(@Req() req: AuthenticatedRequest, @Param('id') id: string, @Body() body: { emoji: string }) {
    if (!req.claims.person_id) throw new ForbiddenException();
    return this.bulletin.react(req.claims.tenant_id, id, req.claims.person_id, body.emoji);
  }
}
