import { Controller, Get, Query, Req, UseGuards } from '@nestjs/common';
import { AuditService } from './audit.service';
import { SupabaseJwtGuard, type AuthenticatedRequest } from '../auth/supabase-jwt.guard';
import { Roles, RolesGuard } from '../auth/roles.decorator';

@Controller('audit-log')
@UseGuards(SupabaseJwtGuard, RolesGuard)
@Roles('mgmt_admin')
export class AuditController {
  constructor(private readonly audit: AuditService) {}

  @Get()
  list(
    @Req() req: AuthenticatedRequest,
    @Query('entity_type') entityType?: string,
    @Query('entity_id') entityId?: string,
  ) {
    return this.audit.list(req.claims.tenant_id, entityType, entityId);
  }
}
