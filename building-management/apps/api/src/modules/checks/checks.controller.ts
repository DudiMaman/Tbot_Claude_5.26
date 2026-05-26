import { Body, Controller, Get, Param, Post, Query, Req, UseGuards } from '@nestjs/common';
import { ChecksService } from './checks.service';
import { SupabaseJwtGuard, type AuthenticatedRequest } from '../auth/supabase-jwt.guard';
import { ReceiveCheckSchema, BounceCheckSchema } from '@bm/shared';
import { ZodPipe } from '../../common/zod.pipe';
import { Roles, RolesGuard } from '../auth/roles.decorator';

@Controller('checks')
@UseGuards(SupabaseJwtGuard, RolesGuard)
@Roles('mgmt_admin', 'mgmt_member')
export class ChecksController {
  constructor(private readonly checks: ChecksService) {}

  @Post()
  receive(
    @Req() req: AuthenticatedRequest,
    @Body(new ZodPipe(ReceiveCheckSchema)) body: any,
  ) {
    return this.checks.receive(req.claims.tenant_id, req.claims.sub, body);
  }

  @Post('batches')
  createBatch(
    @Req() req: AuthenticatedRequest,
    @Body() body: {
      building_id: string;
      bank_account_iban: string;
      deposit_date: string;
      check_ids: string[];
    },
  ) {
    return this.checks.createBatch(
      req.claims.tenant_id,
      req.claims.sub,
      body.building_id,
      body.bank_account_iban,
      body.deposit_date,
      body.check_ids,
    );
  }

  @Post('bounce')
  bounce(
    @Req() req: AuthenticatedRequest,
    @Body(new ZodPipe(BounceCheckSchema)) body: any,
  ) {
    return this.checks.markBounced(req.claims.tenant_id, body);
  }

  @Post('bounced/:id/replacement')
  linkReplacement(
    @Req() req: AuthenticatedRequest,
    @Param('id') id: string,
    @Body() body: { replacement_check_id: string },
  ) {
    return this.checks.linkReplacement(req.claims.tenant_id, id, body.replacement_check_id);
  }

  @Get()
  list(
    @Req() req: AuthenticatedRequest,
    @Query('building_id') buildingId?: string,
    @Query('status') status?: string,
  ) {
    return this.checks.list(req.claims.tenant_id, buildingId, status);
  }

  @Get('bounced')
  listBounced(@Req() req: AuthenticatedRequest) {
    return this.checks.listBounced(req.claims.tenant_id);
  }
}
