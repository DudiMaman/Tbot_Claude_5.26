import { Injectable, ForbiddenException, NotFoundException } from '@nestjs/common';
import { DbService } from '../../db/db.service';
import { createHmac } from 'node:crypto';
import type { CreatePoll } from '@bm/shared';

@Injectable()
export class PollsService {
  constructor(private readonly db: DbService) {}

  async create(tenantId: string, authorUserId: string, input: CreatePoll) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const { rows } = await c.query(
        `insert into polls
          (tenant_id, building_id, author_user_id, title, description, type, options,
           eligibility, anonymous, opens_at, closes_at, requires_signature, status)
         values ($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9,$10,$11,$12,'open')
         returning *`,
        [
          tenantId,
          input.building_id,
          authorUserId,
          input.title,
          input.description ?? null,
          input.type,
          JSON.stringify(input.options),
          input.eligibility,
          input.anonymous,
          input.opens_at,
          input.closes_at,
          input.requires_signature,
        ],
      );
      return rows[0];
    });
  }

  async vote(
    tenantId: string,
    pollId: string,
    personId: string,
    apartmentId: string,
    choice: unknown,
    signature?: string,
  ) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'resident' }, async (c) => {
      // Eligibility check
      const pollRes = await c.query<{ eligibility: string; anonymous: boolean }>(
        `select eligibility, anonymous from polls where id = $1 and status = 'open'`,
        [pollId],
      );
      if (pollRes.rows.length === 0) throw new NotFoundException('Poll not open');
      const poll = pollRes.rows[0]!;

      const assignRes = await c.query<{ role: string; is_bill_payer: boolean }>(
        `select role, is_bill_payer from apartment_assignments
         where apartment_id = $1 and person_id = $2 and status = 'active'
         limit 1`,
        [apartmentId, personId],
      );
      const assign = assignRes.rows[0];
      if (!assign) throw new ForbiddenException('No active assignment');
      if (poll.eligibility === 'owner_only' && assign.role !== 'owner') {
        throw new ForbiddenException('Owner-only poll');
      }
      if (poll.eligibility === 'bill_payer_only' && !assign.is_bill_payer) {
        throw new ForbiddenException('Bill-payer-only poll');
      }

      const personHash = poll.anonymous
        ? createHmac('sha256', `poll:${pollId}`).update(personId).digest('hex')
        : null;

      const { rows } = await c.query(
        `insert into votes (tenant_id, poll_id, person_id, person_id_hash, apartment_id, choice, signature_blob, voted_at)
         values ($1, $2, $3, $4, $5, $6::jsonb, $7, now())
         on conflict do nothing returning *`,
        [
          tenantId,
          pollId,
          poll.anonymous ? null : personId,
          personHash,
          apartmentId,
          JSON.stringify(choice),
          signature ?? null,
        ],
      );
      return rows[0];
    });
  }

  async results(tenantId: string, pollId: string) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const { rows } = await c.query(
        `select choice, count(*)::int as votes from votes where poll_id = $1 group by choice`,
        [pollId],
      );
      return rows;
    });
  }
}
