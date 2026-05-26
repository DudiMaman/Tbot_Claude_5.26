import { Body, Controller, Get, Param, Post, Query, Req, UseGuards } from '@nestjs/common';
import { PeopleService } from './people.service';
import { SupabaseJwtGuard, type AuthenticatedRequest } from '../auth/supabase-jwt.guard';
import { CreatePersonSchema } from '@bm/shared';
import { ZodPipe } from '../../common/zod.pipe';

@Controller('people')
@UseGuards(SupabaseJwtGuard)
export class PeopleController {
  constructor(private readonly people: PeopleService) {}

  @Post()
  create(@Req() req: AuthenticatedRequest, @Body(new ZodPipe(CreatePersonSchema)) body: any) {
    return this.people.create(req.claims.tenant_id, body);
  }

  @Get()
  list(@Req() req: AuthenticatedRequest, @Query('q') q?: string) {
    return this.people.list(req.claims.tenant_id, q);
  }

  @Get(':id')
  findOne(@Req() req: AuthenticatedRequest, @Param('id') id: string) {
    return this.people.findOne(req.claims.tenant_id, id);
  }

  @Post('claim')
  claim(
    @Req() req: AuthenticatedRequest,
    @Body() body: {
      phone: string;
      full_name: string;
      building_id: string;
      unit_number: string;
      role: 'owner' | 'renter' | 'family_member';
    },
  ) {
    return this.people.claim(
      req.claims.tenant_id,
      req.claims.sub,
      body.phone,
      body.full_name,
      body.building_id,
      body.unit_number,
      body.role,
    );
  }
}
