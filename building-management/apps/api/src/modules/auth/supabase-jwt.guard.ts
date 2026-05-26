import { CanActivate, ExecutionContext, Injectable, UnauthorizedException, Logger } from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { jwtVerify, type JWTPayload } from 'jose';
import type { Request } from 'express';
import { PUBLIC_KEY } from './public.decorator';

export interface AuthenticatedRequest extends Request {
  claims: {
    sub: string;
    tenant_id: string;
    role: 'mgmt_admin' | 'mgmt_member' | 'maintenance' | 'resident';
    person_id?: string;
    building_ids?: string[];
    apartment_ids?: string[];
    permissions?: string[];
  };
}

@Injectable()
export class SupabaseJwtGuard implements CanActivate {
  private readonly logger = new Logger(SupabaseJwtGuard.name);
  private readonly jwtSecret: Uint8Array | null;

  constructor(private readonly reflector: Reflector) {
    const secret = process.env.SUPABASE_JWT_SECRET;
    this.jwtSecret = secret ? new TextEncoder().encode(secret) : null;
  }

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const isPublic = this.reflector.getAllAndOverride<boolean>(PUBLIC_KEY, [
      context.getHandler(),
      context.getClass(),
    ]);
    if (isPublic) return true;

    const req = context.switchToHttp().getRequest<AuthenticatedRequest>();
    const auth = req.headers.authorization;
    if (!auth?.startsWith('Bearer ')) {
      throw new UnauthorizedException('Missing bearer token');
    }
    const token = auth.slice('Bearer '.length);

    if (!this.jwtSecret) {
      // Development mode: accept unsigned base64-encoded JSON for local testing.
      try {
        const payload = JSON.parse(Buffer.from(token, 'base64').toString('utf-8'));
        this.attachClaims(req, payload);
        return true;
      } catch {
        throw new UnauthorizedException('Invalid dev token');
      }
    }

    try {
      const { payload } = await jwtVerify(token, this.jwtSecret, {
        audience: process.env.JWT_AUDIENCE ?? 'authenticated',
      });
      this.attachClaims(req, payload);
      return true;
    } catch (err) {
      this.logger.warn(`JWT verify failed: ${(err as Error).message}`);
      throw new UnauthorizedException('Invalid token');
    }
  }

  private attachClaims(req: AuthenticatedRequest, payload: JWTPayload & Record<string, unknown>) {
    const tenantId = payload.tenant_id as string | undefined;
    const role = payload.role as AuthenticatedRequest['claims']['role'] | undefined;
    if (!tenantId || !role) {
      throw new UnauthorizedException('Token missing tenant_id or role');
    }
    req.claims = {
      sub: String(payload.sub),
      tenant_id: tenantId,
      role,
      person_id: payload.person_id as string | undefined,
      building_ids: payload.building_ids as string[] | undefined,
      apartment_ids: payload.apartment_ids as string[] | undefined,
      permissions: payload.permissions as string[] | undefined,
    };
  }
}
