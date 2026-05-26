import { Injectable } from '@nestjs/common';
import { DbService } from '../../db/db.service';
import type { CreateBulletin } from '@bm/shared';

@Injectable()
export class BulletinService {
  constructor(private readonly db: DbService) {}

  async create(tenantId: string, authorUserId: string, input: CreateBulletin) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const { rows } = await c.query(
        `insert into bulletin_posts
          (tenant_id, building_id, author_user_id, title, body_md, pinned, pinned_until, expires_at,
           audience, reactions_enabled, comments_enabled, status, published_at)
         values ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10,$11,'published', now())
         returning *`,
        [
          tenantId,
          input.building_id,
          authorUserId,
          input.title,
          input.body_md,
          input.pinned,
          input.pinned_until ?? null,
          input.expires_at ?? null,
          JSON.stringify(input.audience),
          input.reactions_enabled,
          input.comments_enabled,
        ],
      );
      return rows[0];
    });
  }

  async listForBuilding(tenantId: string, buildingId: string) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const { rows } = await c.query(
        `select * from bulletin_posts
         where building_id = $1 and status = 'published'
           and (expires_at is null or expires_at > now())
         order by pinned desc, published_at desc nulls last`,
        [buildingId],
      );
      return rows;
    });
  }

  async react(tenantId: string, postId: string, personId: string, emoji: string) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'resident' }, async (c) => {
      await c.query(
        `insert into bulletin_reactions (tenant_id, post_id, person_id, emoji)
         values ($1, $2, $3, $4) on conflict do nothing`,
        [tenantId, postId, personId, emoji],
      );
      return { ok: true };
    });
  }
}
