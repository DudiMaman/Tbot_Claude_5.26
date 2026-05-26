import { Body, Controller, Get, Post, Req, UseGuards } from '@nestjs/common';
import { VendorsService } from './vendors.service';
import { SupabaseJwtGuard, type AuthenticatedRequest } from '../auth/supabase-jwt.guard';
import { Roles, RolesGuard } from '../auth/roles.decorator';

@Controller('vendors')
@UseGuards(SupabaseJwtGuard, RolesGuard)
@Roles('mgmt_admin', 'mgmt_member')
export class VendorsController {
  constructor(private readonly vendors: VendorsService) {}

  @Post()
  create(@Req() req: AuthenticatedRequest, @Body() body: any) {
    return this.vendors.create(req.claims.tenant_id, body);
  }
  @Get()
  list(@Req() req: AuthenticatedRequest) {
    return this.vendors.list(req.claims.tenant_id);
  }
  @Post('invoices')
  uploadInvoice(@Req() req: AuthenticatedRequest, @Body() body: any) {
    return this.vendors.uploadInvoice(req.claims.tenant_id, body);
  }
  @Post('masav')
  generateMasav(@Req() req: AuthenticatedRequest, @Body() body: { invoice_ids: string[]; payer: any; institution_code: string }) {
    return this.vendors.generateMasav(req.claims.tenant_id, body.invoice_ids, body.payer, body.institution_code);
  }
}
