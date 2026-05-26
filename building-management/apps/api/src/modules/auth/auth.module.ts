import { Global, Module } from '@nestjs/common';
import { SupabaseJwtGuard } from './supabase-jwt.guard';
import { RlsContextInterceptor } from './rls-context.interceptor';

@Global()
@Module({
  providers: [SupabaseJwtGuard, RlsContextInterceptor],
  exports: [SupabaseJwtGuard, RlsContextInterceptor],
})
export class AuthModule {}
