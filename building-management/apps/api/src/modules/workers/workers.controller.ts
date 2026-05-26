import { Body, Controller, Get, Param, Post, Req, UseGuards } from '@nestjs/common';
import { WorkersService } from './workers.service';
import { SupabaseJwtGuard, type AuthenticatedRequest } from '../auth/supabase-jwt.guard';
import { Roles, RolesGuard } from '../auth/roles.decorator';

@Controller('workers')
@UseGuards(SupabaseJwtGuard, RolesGuard)
export class WorkersController {
  constructor(private readonly workers: WorkersService) {}

  @Roles('mgmt_admin', 'mgmt_member')
  @Post()
  create(@Req() req: AuthenticatedRequest, @Body() body: any) {
    return this.workers.create(req.claims.tenant_id, body);
  }

  @Roles('mgmt_admin', 'mgmt_member')
  @Get()
  list(@Req() req: AuthenticatedRequest) {
    return this.workers.list(req.claims.tenant_id);
  }

  @Roles('mgmt_admin', 'mgmt_member')
  @Post(':id/assign-building')
  assign(
    @Req() req: AuthenticatedRequest,
    @Param('id') id: string,
    @Body() body: { building_id: string },
  ) {
    return this.workers.assignToBuilding(req.claims.tenant_id, id, body.building_id);
  }

  @Roles('maintenance')
  @Get('me/today')
  myToday(@Req() req: AuthenticatedRequest) {
    // worker_id is fetched from supabase_user_id in real impl — simplified here
    return this.workers.todaySchedule(req.claims.tenant_id, req.claims.sub);
  }
}
