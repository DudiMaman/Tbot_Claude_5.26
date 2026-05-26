import { Body, Controller, Get, Param, Patch, Post, Query, Req, UseGuards } from '@nestjs/common';
import { TasksService } from './tasks.service';
import { SupabaseJwtGuard, type AuthenticatedRequest } from '../auth/supabase-jwt.guard';

@Controller('tasks')
@UseGuards(SupabaseJwtGuard)
export class TasksController {
  constructor(private readonly tasks: TasksService) {}

  @Post()
  create(@Req() req: AuthenticatedRequest, @Body() body: any) {
    return this.tasks.create(req.claims.tenant_id, body);
  }

  @Get()
  list(
    @Req() req: AuthenticatedRequest,
    @Query('worker_id') worker_id?: string,
    @Query('building_id') building_id?: string,
    @Query('status') status?: string,
  ) {
    return this.tasks.list(req.claims.tenant_id, { worker_id, building_id, status });
  }

  @Patch(':id/status')
  updateStatus(
    @Req() req: AuthenticatedRequest,
    @Param('id') id: string,
    @Body() body: { status: any },
  ) {
    return this.tasks.updateStatus(req.claims.tenant_id, id, body.status);
  }

  @Patch(':id/assign')
  assign(
    @Req() req: AuthenticatedRequest,
    @Param('id') id: string,
    @Body() body: { worker_id: string },
  ) {
    return this.tasks.assign(req.claims.tenant_id, id, body.worker_id);
  }
}
