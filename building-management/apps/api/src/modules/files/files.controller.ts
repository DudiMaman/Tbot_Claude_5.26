import { Body, Controller, Get, Param, Post, Req, UseGuards } from '@nestjs/common';
import { FilesService } from './files.service';
import { SupabaseJwtGuard, type AuthenticatedRequest } from '../auth/supabase-jwt.guard';

@Controller('files')
@UseGuards(SupabaseJwtGuard)
export class FilesController {
  constructor(private readonly files: FilesService) {}

  @Post('upload-intent')
  intent(@Req() req: AuthenticatedRequest, @Body() body: { bucket: string; path: string; mime: string; size_bytes: number; pii_tag?: any }) {
    return this.files.createUploadIntent(
      req.claims.tenant_id,
      req.claims.role === 'resident' ? null : req.claims.sub,
      req.claims.person_id ?? null,
      body.bucket,
      body.path,
      body.mime,
      body.size_bytes,
      body.pii_tag,
    );
  }

  @Get(':id/url')
  async signed(@Param('id') id: string) {
    const url = await this.files.getSignedUrl(id);
    return { url };
  }
}
