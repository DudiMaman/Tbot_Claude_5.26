import { Body, Controller, ForbiddenException, Get, Post, Query, Req, UseGuards } from '@nestjs/common';
import { AddonsService } from './addons.service';
import { SupabaseJwtGuard, type AuthenticatedRequest } from '../auth/supabase-jwt.guard';

@Controller('addons')
@UseGuards(SupabaseJwtGuard)
export class AddonsController {
  constructor(private readonly addons: AddonsService) {}

  @Post('products')
  createProduct(@Req() req: AuthenticatedRequest, @Body() body: any) {
    if (req.claims.role === 'resident') throw new ForbiddenException();
    return this.addons.createProduct(req.claims.tenant_id, body);
  }

  @Get('products')
  list(@Req() req: AuthenticatedRequest, @Query('building_id') buildingId: string) {
    return this.addons.listForBuilding(req.claims.tenant_id, buildingId);
  }

  @Post('orders')
  order(@Req() req: AuthenticatedRequest, @Body() body: any) {
    if (!req.claims.person_id) throw new ForbiddenException();
    return this.addons.order(req.claims.tenant_id, req.claims.person_id, body);
  }
}
