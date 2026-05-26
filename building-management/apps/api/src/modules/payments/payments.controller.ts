import { Body, Controller, Post, Req, UseGuards, ForbiddenException } from '@nestjs/common';
import { PaymentsService } from './payments.service';
import { SupabaseJwtGuard, type AuthenticatedRequest } from '../auth/supabase-jwt.guard';
import { CreatePaymentSchema } from '@bm/shared';
import { ZodPipe } from '../../common/zod.pipe';

@Controller('payments')
@UseGuards(SupabaseJwtGuard)
export class PaymentsController {
  constructor(private readonly payments: PaymentsService) {}

  @Post()
  pay(
    @Req() req: AuthenticatedRequest,
    @Body(new ZodPipe(CreatePaymentSchema)) body: any,
  ) {
    if (req.claims.role !== 'resident' || !req.claims.person_id) {
      throw new ForbiddenException('Only residents can call this endpoint');
    }
    return this.payments.payCharge(req.claims.tenant_id, req.claims.person_id, body);
  }

  @Post('offline')
  offline(
    @Req() req: AuthenticatedRequest,
    @Body() body: { charge_id: string; method: 'cash' | 'check' | 'wire' | 'other'; amount: number; notes?: string },
  ) {
    if (req.claims.role !== 'mgmt_admin' && req.claims.role !== 'mgmt_member') {
      throw new ForbiddenException('mgmt-only endpoint');
    }
    return this.payments.recordOfflinePayment(
      req.claims.tenant_id,
      req.claims.sub,
      body.charge_id,
      body.method,
      body.amount,
      body.notes,
    );
  }
}
