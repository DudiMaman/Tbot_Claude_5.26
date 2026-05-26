/**
 * AccessService — one-tap gate open from resident app, guest codes.
 * See SPEC §20.
 */
import { Injectable, Logger, ForbiddenException, NotFoundException } from '@nestjs/common';
import { DbService } from '../../db/db.service';
import { HttpWebhookProvider } from './providers/http-webhook.provider';
import { MockProvider } from './providers/mock.provider';
import type { AccessGate } from '@bm/db';
import { randomBytes } from 'node:crypto';

export interface OpenGateResult {
  ok: boolean;
  latency_ms: number;
  reason?: string;
}

@Injectable()
export class AccessService {
  private readonly logger = new Logger(AccessService.name);

  constructor(
    private readonly db: DbService,
    private readonly http: HttpWebhookProvider,
    private readonly mock: MockProvider,
  ) {}

  /**
   * Open the gate as the calling person. Validates that the person is
   * an active occupant of the gate's building.
   */
  async openAsPerson(tenantId: string, personId: string, gateId: string): Promise<OpenGateResult> {
    const gate = await this.fetchGate(tenantId, gateId);
    const ok = await this.canOpen(tenantId, personId, gate);
    if (!ok) throw new ForbiddenException('Not authorized to open this gate');
    return this.executeOpen(tenantId, gate, { person_id: personId, source: 'app' });
  }

  async openAsGuest(tenantId: string, code: string, gateId: string): Promise<OpenGateResult> {
    const gate = await this.fetchGate(tenantId, gateId);
    const codeOk = await this.consumeGuestCode(tenantId, code, gateId);
    if (!codeOk) throw new ForbiddenException('Invalid or expired code');
    return this.executeOpen(tenantId, gate, { guest_code: code, source: 'code' });
  }

  async createGuestCode(
    tenantId: string,
    createdByPersonId: string,
    buildingId: string,
    gateId: string | null,
    validHours: number = 24,
    maxUses: number = 1,
  ) {
    const code = randomBytes(3).toString('hex').toUpperCase();
    const validTo = new Date(Date.now() + validHours * 3600_000);
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'resident' }, async (c) => {
      const { rows } = await c.query(
        `insert into guest_codes (tenant_id, building_id, gate_id, code, created_by_person_id, valid_to, max_uses)
         values ($1, $2, $3, $4, $5, $6, $7) returning *`,
        [tenantId, buildingId, gateId, code, createdByPersonId, validTo, maxUses],
      );
      return rows[0];
    });
  }

  async listGates(tenantId: string, buildingId?: string) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      if (buildingId) {
        const { rows } = await c.query(
          `select * from access_gates where building_id = $1 order by name`,
          [buildingId],
        );
        return rows;
      }
      const { rows } = await c.query(`select * from access_gates order by name`);
      return rows;
    });
  }

  private async fetchGate(tenantId: string, gateId: string): Promise<AccessGate> {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const { rows } = await c.query<AccessGate>(`select * from access_gates where id = $1`, [gateId]);
      if (rows.length === 0) throw new NotFoundException('Gate not found');
      return rows[0]!;
    });
  }

  private async canOpen(tenantId: string, personId: string, gate: AccessGate): Promise<boolean> {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const { rows } = await c.query(
        `select 1 from apartment_assignments aa
         join apartments a on a.id = aa.apartment_id
         where a.building_id = $1
           and aa.person_id = $2
           and aa.is_occupant = true
           and aa.status = 'active'
           and (aa.valid_to is null or aa.valid_to >= current_date)
         limit 1`,
        [gate.building_id, personId],
      );
      return rows.length > 0;
    });
  }

  private async consumeGuestCode(tenantId: string, code: string, gateId: string): Promise<boolean> {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const { rows } = await c.query<{ id: string; uses: number; max_uses: number }>(
        `select id, uses, max_uses from guest_codes
         where code = $1 and (gate_id = $2 or gate_id is null)
           and status = 'active' and valid_from <= now() and valid_to >= now()
         limit 1`,
        [code, gateId],
      );
      if (rows.length === 0) return false;
      const c2 = rows[0]!;
      if (c2.uses >= c2.max_uses) return false;
      await c.query(
        `update guest_codes set uses = uses + 1, status = case when uses + 1 >= max_uses then 'used' else status end where id = $1`,
        [c2.id],
      );
      return true;
    });
  }

  private async executeOpen(
    tenantId: string,
    gate: AccessGate,
    actor: { person_id?: string; guest_code?: string; source: string },
  ): Promise<OpenGateResult> {
    const start = Date.now();
    const provider = this.pickProvider(gate);
    const result = await provider.open(gate);
    const latency_ms = Date.now() - start;

    await this.db.query(
      `insert into access_events (tenant_id, gate_id, person_id, action, source, latency_ms)
       values ($1, $2, $3, $4, $5, $6)`,
      [
        tenantId,
        gate.id,
        actor.person_id ?? null,
        result.ok ? 'open' : 'deny',
        actor.source,
        latency_ms,
      ],
    );

    return { ok: result.ok, latency_ms, reason: result.reason };
  }

  private pickProvider(gate: AccessGate) {
    if (gate.provider === 'http_webhook') return this.http;
    return this.mock;
  }
}
