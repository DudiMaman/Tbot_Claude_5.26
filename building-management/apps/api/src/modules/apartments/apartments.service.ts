import { Injectable, NotFoundException, BadRequestException } from '@nestjs/common';
import { DbService } from '../../db/db.service';
import type { CreateApartment, CreateAssignment, CreateRentalContract } from '@bm/shared';

@Injectable()
export class ApartmentsService {
  constructor(private readonly db: DbService) {}

  async create(tenantId: string, input: CreateApartment) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      const { rows } = await client.query(
        `insert into apartments (tenant_id, building_id, unit_number, floor, size_sqm, num_rooms, monthly_dues_amount)
         values ($1, $2, $3, $4, $5, $6, $7)
         returning *`,
        [
          tenantId,
          input.building_id,
          input.unit_number,
          input.floor ?? null,
          input.size_sqm ?? null,
          input.num_rooms ?? null,
          input.monthly_dues_amount ?? null,
        ],
      );
      return rows[0];
    });
  }

  async list(tenantId: string, buildingId?: string) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      const { rows } = buildingId
        ? await client.query(
            `select * from apartments where building_id = $1 and deleted_at is null order by unit_number`,
            [buildingId],
          )
        : await client.query(
            `select * from apartments where deleted_at is null order by unit_number`,
          );
      return rows;
    });
  }

  async findOne(tenantId: string, apartmentId: string) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      const { rows } = await client.query(
        `select * from apartments where id = $1 and deleted_at is null`,
        [apartmentId],
      );
      if (rows.length === 0) throw new NotFoundException('Apartment not found');
      return rows[0];
    });
  }

  async addAssignment(tenantId: string, input: CreateAssignment) {
    if (input.role === 'renter' && !input.is_occupant) {
      throw new BadRequestException('renter must be occupant');
    }
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      const { rows } = await client.query(
        `insert into apartment_assignments
          (tenant_id, apartment_id, person_id, role, is_primary, is_occupant, is_bill_payer, share_pct, valid_from, valid_to)
         values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
         returning *`,
        [
          tenantId,
          input.apartment_id,
          input.person_id,
          input.role,
          input.is_primary,
          input.is_occupant,
          input.is_bill_payer,
          input.share_pct ?? null,
          input.valid_from ?? new Date().toISOString().slice(0, 10),
          input.valid_to ?? null,
        ],
      );
      return rows[0];
    });
  }

  async endAssignment(tenantId: string, assignmentId: string, endDate?: string) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      const { rows } = await client.query(
        `update apartment_assignments
         set valid_to = coalesce($2, current_date),
             status = 'ended',
             is_bill_payer = false,
             updated_at = now()
         where id = $1
         returning *`,
        [assignmentId, endDate ?? null],
      );
      if (rows.length === 0) throw new NotFoundException('Assignment not found');
      return rows[0];
    });
  }

  async createRentalContract(tenantId: string, input: CreateRentalContract) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (client) => {
      const { rows } = await client.query(
        `insert into rental_contracts
          (tenant_id, apartment_id, owner_person_id, renter_person_id, start_date, end_date,
           monthly_rent, vaad_responsibility, split_renter_pct, contract_file_id, status)
         values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'active')
         returning *`,
        [
          tenantId,
          input.apartment_id,
          input.owner_person_id,
          input.renter_person_id,
          input.start_date,
          input.end_date ?? null,
          input.monthly_rent ?? null,
          input.vaad_responsibility,
          input.split_renter_pct ?? null,
          input.contract_file_id ?? null,
        ],
      );
      return rows[0];
    });
  }
}
