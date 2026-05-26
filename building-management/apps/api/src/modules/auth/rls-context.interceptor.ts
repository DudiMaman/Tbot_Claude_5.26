import { CallHandler, ExecutionContext, Injectable, NestInterceptor } from '@nestjs/common';
import type { Observable } from 'rxjs';
import type { AuthenticatedRequest } from './supabase-jwt.guard';

/**
 * Stores the JWT claims on the request so services can call
 * DbService.withTenantContext(req.claims, ...) seamlessly.
 *
 * This interceptor is light: actual SET LOCAL of jwt claims happens
 * per-transaction inside DbService.withTenantContext.
 */
@Injectable()
export class RlsContextInterceptor implements NestInterceptor {
  intercept(context: ExecutionContext, next: CallHandler): Observable<unknown> {
    const req = context.switchToHttp().getRequest<AuthenticatedRequest>();
    // No-op: claims already on req from SupabaseJwtGuard.
    void req;
    return next.handle();
  }
}
