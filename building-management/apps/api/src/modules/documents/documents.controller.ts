import { Body, Controller, Get, Param, Post, Query, Req, UseGuards } from '@nestjs/common';
import { DocumentsService } from './documents.service';
import { SupabaseJwtGuard, type AuthenticatedRequest } from '../auth/supabase-jwt.guard';
import { UploadDocumentSchema } from '@bm/shared';
import { ZodPipe } from '../../common/zod.pipe';
import { Roles, RolesGuard } from '../auth/roles.decorator';

@Controller('documents')
@UseGuards(SupabaseJwtGuard, RolesGuard)
@Roles('mgmt_admin', 'mgmt_member')
export class DocumentsController {
  constructor(private readonly docs: DocumentsService) {}

  @Post()
  upload(@Req() req: AuthenticatedRequest, @Body(new ZodPipe(UploadDocumentSchema)) body: any) {
    return this.docs.upload(req.claims.tenant_id, req.claims.sub, body);
  }

  @Post(':id/versions')
  addVersion(
    @Req() req: AuthenticatedRequest,
    @Param('id') id: string,
    @Body() body: { file_id: string; notes?: string },
  ) {
    return this.docs.addVersion(req.claims.tenant_id, req.claims.sub, id, body.file_id, body.notes);
  }

  @Get()
  list(
    @Req() req: AuthenticatedRequest,
    @Query('building_id') buildingId: string,
    @Query('category') category?: string,
  ) {
    return this.docs.list(req.claims.tenant_id, buildingId, category);
  }

  @Get('expiring-soon')
  expiringSoon(@Req() req: AuthenticatedRequest, @Query('days') days?: string) {
    return this.docs.expiringSoon(req.claims.tenant_id, days ? Number(days) : 30);
  }
}
