import { Body, Controller, Get, Param, Patch, Post, Query, Req, UseGuards } from '@nestjs/common';
import { TicketsService } from './tickets.service';
import { SupabaseJwtGuard, type AuthenticatedRequest } from '../auth/supabase-jwt.guard';
import { CreateTicketSchema } from '@bm/shared';
import { ZodPipe } from '../../common/zod.pipe';

@Controller('tickets')
@UseGuards(SupabaseJwtGuard)
export class TicketsController {
  constructor(private readonly tickets: TicketsService) {}

  @Post()
  create(@Req() req: AuthenticatedRequest, @Body(new ZodPipe(CreateTicketSchema)) body: any) {
    return this.tickets.create(req.claims.tenant_id, req.claims.person_id ?? null, body);
  }

  @Get()
  list(
    @Req() req: AuthenticatedRequest,
    @Query('building_id') buildingId?: string,
    @Query('status') status?: string,
  ) {
    return this.tickets.list(req.claims.tenant_id, buildingId, status);
  }

  @Get(':id')
  findOne(@Req() req: AuthenticatedRequest, @Param('id') id: string) {
    return this.tickets.findOne(req.claims.tenant_id, id);
  }

  @Patch(':id/status')
  updateStatus(
    @Req() req: AuthenticatedRequest,
    @Param('id') id: string,
    @Body() body: { status: any; note?: string },
  ) {
    return this.tickets.updateStatus(req.claims.tenant_id, id, body.status, body.note);
  }

  @Post(':id/rate')
  rate(
    @Req() req: AuthenticatedRequest,
    @Param('id') id: string,
    @Body() body: { rating: number; comment?: string },
  ) {
    return this.tickets.rate(req.claims.tenant_id, id, body.rating, body.comment);
  }
}
