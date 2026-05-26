import { Injectable, NotFoundException } from '@nestjs/common';
import { DbService } from '../../db/db.service';
import { toE164 } from '@bm/shared/phone';
import type { CreatePerson } from '@bm/shared';
import type { Person } from '@bm/db';

@Injectable()
export class PeopleService {
  constructor(private readonly db: DbService) {}

  async create(tenantId: string, input: CreatePerson): Promise<Person> {
    const phone = input.phone_e164 ? toE164(input.phone_e164) : null;
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const { rows } = await c.query<Person>(
        `insert into people (tenant_id, full_name, phone_e164, email, language)
         values ($1, $2, $3, $4, $5) returning *`,
        [tenantId, input.full_name, phone, input.email ?? null, input.language ?? 'he'],
      );
      return rows[0]!;
    });
  }

  async list(tenantId: string, q?: string) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      if (q) {
        const { rows } = await c.query<Person>(
          `select * from people where deleted_at is null
           and (full_name ilike $1 or phone_e164 ilike $1 or email ilike $1)
           order by full_name limit 100`,
          [`%${q}%`],
        );
        return rows;
      }
      const { rows } = await c.query<Person>(
        `select * from people where deleted_at is null order by full_name limit 100`,
      );
      return rows;
    });
  }

  async findOne(tenantId: string, id: string): Promise<Person> {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const { rows } = await c.query<Person>(`select * from people where id = $1`, [id]);
      if (rows.length === 0) throw new NotFoundException();
      return rows[0]!;
    });
  }

  async findByPhone(tenantId: string, phone: string): Promise<Person | null> {
    const e164 = toE164(phone);
    if (!e164) return null;
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const { rows } = await c.query<Person>(
        `select * from people where phone_e164 = $1 and deleted_at is null limit 1`,
        [e164],
      );
      return rows[0] ?? null;
    });
  }

  /** Resident self-claim — links auth.users to a Person via phone matching. */
  async claim(
    tenantId: string,
    supabaseUserId: string,
    phone: string,
    fullName: string,
    buildingId: string,
    unitNumber: string,
    role: 'owner' | 'renter' | 'family_member',
  ): Promise<{ person: Person; pending: boolean }> {
    const e164 = toE164(phone);
    if (!e164) throw new Error('invalid phone');
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      // Find apartment
      const aptRes = await c.query<{ id: string }>(
        `select id from apartments where building_id = $1 and unit_number = $2 and deleted_at is null`,
        [buildingId, unitNumber],
      );
      if (aptRes.rows.length === 0) throw new NotFoundException('Apartment not found');
      const apartmentId = aptRes.rows[0]!.id;

      // Find existing person by phone
      const existing = await c.query<Person>(
        `select * from people where phone_e164 = $1 limit 1`,
        [e164],
      );
      let person = existing.rows[0];
      const isExisting = !!person;

      if (!person) {
        const ins = await c.query<Person>(
          `insert into people (tenant_id, full_name, phone_e164, claim_status, claim_method, supabase_user_id)
           values ($1, $2, $3, 'pending', 'qr', $4) returning *`,
          [tenantId, fullName, e164, supabaseUserId],
        );
        person = ins.rows[0]!;
      } else if (!person.supabase_user_id) {
        await c.query(`update people set supabase_user_id = $2 where id = $1`, [
          person.id,
          supabaseUserId,
        ]);
      }

      // Check existing active assignment
      const existingAssign = await c.query(
        `select 1 from apartment_assignments
         where apartment_id = $1 and person_id = $2 and status = 'active' and valid_to is null`,
        [apartmentId, person.id],
      );

      const autoApprove = isExisting && existingAssign.rows.length > 0;
      const status = autoApprove ? 'active' : 'pending';

      if (existingAssign.rows.length === 0) {
        await c.query(
          `insert into apartment_assignments
            (tenant_id, apartment_id, person_id, role, is_primary, is_occupant, is_bill_payer, valid_from, status)
           values ($1, $2, $3, $4, false, $5, false, current_date, $6)`,
          [tenantId, apartmentId, person.id, role, role !== 'owner' || role === 'owner', status],
        );
      }
      if (autoApprove) {
        await c.query(`update people set claim_status = 'approved' where id = $1`, [person.id]);
      }
      return { person, pending: !autoApprove };
    });
  }
}
