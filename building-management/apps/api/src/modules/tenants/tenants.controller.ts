import { Body, Controller, Get, Post, Put, Req, UseGuards } from '@nestjs/common';
import { TenantsService } from './tenants.service';
import { SupabaseJwtGuard, type AuthenticatedRequest } from '../auth/supabase-jwt.guard';
import { Public } from '../auth/public.decorator';
import { CreateTenantSchema } from '@bm/shared';
import { ZodPipe } from '../../common/zod.pipe';

@Controller('tenants')
export class TenantsController {
  constructor(private readonly tenants: TenantsService) {}

  @Public()
  @Post('signup')
  signup(
    @Body(new ZodPipe(CreateTenantSchema.extend({ admin_user_id: (CreateTenantSchema.shape.billing_email as any) }) as any)) body: any,
  ) {
    return this.tenants.signup(body);
  }

  @UseGuards(SupabaseJwtGuard)
  @Get('me')
  me(@Req() req: AuthenticatedRequest) {
    return this.tenants.findOne(req.claims.tenant_id);
  }

  @UseGuards(SupabaseJwtGuard)
  @Put('me/branding')
  updateBranding(@Req() req: AuthenticatedRequest, @Body() body: Record<string, unknown>) {
    return this.tenants.updateBranding(req.claims.tenant_id, body);
  }
}
