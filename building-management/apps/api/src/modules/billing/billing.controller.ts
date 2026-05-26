import { Body, Controller, Get, Param, Post, Query, Req, UseGuards } from '@nestjs/common';
import { BillingService } from './billing.service';
import { SupabaseJwtGuard, type AuthenticatedRequest } from '../auth/supabase-jwt.guard';
import { CreateChargeScheduleSchema } from '@bm/shared';
import { ZodPipe } from '../../common/zod.pipe';
import { Roles, RolesGuard } from '../auth/roles.decorator';

@Controller('charge-schedules')
@UseGuards(SupabaseJwtGuard, RolesGuard)
@Roles('mgmt_admin', 'mgmt_member')
export class BillingController {
  constructor(private readonly billing: BillingService) {}

  @Post()
  create(
    @Req() req: AuthenticatedRequest,
    @Body(new ZodPipe(CreateChargeScheduleSchema)) body: any,
  ) {
    return this.billing.createSchedule(req.claims.tenant_id, body);
  }

  @Get()
  list(@Req() req: AuthenticatedRequest, @Query('building_id') buildingId?: string) {
    return this.billing.listSchedules(req.claims.tenant_id, buildingId);
  }

  @Post(':id/dry-run')
  dryRun(
    @Req() req: AuthenticatedRequest,
    @Param('id') id: string,
    @Body() body: { date?: string },
  ) {
    const date = body.date ? new Date(body.date) : new Date();
    return this.billing.dryRun(req.claims.tenant_id, id, date);
  }

  @Post(':id/run')
  run(
    @Req() req: AuthenticatedRequest,
    @Param('id') id: string,
    @Body() body: { due_date?: string },
  ) {
    const due = body.due_date ? new Date(body.due_date) : new Date();
    return this.billing.runCycle(req.claims.tenant_id, id, due);
  }
}
