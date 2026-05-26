import { Body, Controller, Delete, Get, Param, Patch, Post, Req, UseGuards } from '@nestjs/common';
import { BuildingsService } from './buildings.service';
import { SupabaseJwtGuard, type AuthenticatedRequest } from '../auth/supabase-jwt.guard';
import { CreateBuildingSchema } from '@bm/shared';
import { ZodPipe } from '../../common/zod.pipe';
import { Roles, RolesGuard } from '../auth/roles.decorator';

@Controller('buildings')
@UseGuards(SupabaseJwtGuard, RolesGuard)
@Roles('mgmt_admin', 'mgmt_member')
export class BuildingsController {
  constructor(private readonly buildings: BuildingsService) {}

  @Post()
  create(
    @Req() req: AuthenticatedRequest,
    @Body(new ZodPipe(CreateBuildingSchema)) body: any,
  ) {
    return this.buildings.create(req.claims.tenant_id, body);
  }

  @Get()
  list(@Req() req: AuthenticatedRequest) {
    return this.buildings.list(req.claims.tenant_id);
  }

  @Get(':id')
  findOne(@Req() req: AuthenticatedRequest, @Param('id') id: string) {
    return this.buildings.findOne(req.claims.tenant_id, id);
  }

  @Patch(':id')
  update(@Req() req: AuthenticatedRequest, @Param('id') id: string, @Body() body: any) {
    return this.buildings.update(req.claims.tenant_id, id, body);
  }

  @Delete(':id')
  softDelete(@Req() req: AuthenticatedRequest, @Param('id') id: string) {
    return this.buildings.softDelete(req.claims.tenant_id, id);
  }
}
