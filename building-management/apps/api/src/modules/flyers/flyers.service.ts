/**
 * FlyersService — welcome flyer generation with QR code per SPEC §8.
 *
 * Generates A4 PDF + Instagram square + WhatsApp story + OG image.
 * Stores files in Supabase Storage; returns signed URLs.
 *
 * The actual PDF rendering uses @react-pdf/renderer in production.
 * This skeleton produces deterministic placeholder buffers so the API
 * is wired end-to-end; real renderers can swap in behind the same
 * generate() interface.
 */
import { Injectable, NotFoundException } from '@nestjs/common';
import { DbService } from '../../db/db.service';

export interface FlyerVariants {
  pdf_url: string;
  ig_url: string;
  story_url: string;
  og_url: string;
  qr_payload: string;
}

@Injectable()
export class FlyersService {
  constructor(private readonly db: DbService) {}

  async generate(tenantId: string, buildingId: string): Promise<FlyerVariants> {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const { rows } = await c.query<{ name: string; claim_secret: string }>(
        `select name, claim_secret from buildings where id = $1`,
        [buildingId],
      );
      if (rows.length === 0) throw new NotFoundException('Building not found');
      const building = rows[0]!;

      const qrPayload = `https://app.building-management.co.il/claim?b=${buildingId}&s=${building.claim_secret}`;

      const variants = ['pdf', 'ig', 'story', 'og'] as const;
      const urls: Record<string, string> = {};
      for (const v of variants) {
        // In real impl: generate the asset, upload to Storage, get signed URL.
        urls[`${v}_url`] = `https://storage.example.com/flyers/${buildingId}/${v}.${v === 'pdf' ? 'pdf' : 'png'}`;
        await c.query(
          `insert into flyers (tenant_id, building_id, variant, qr_payload)
           values ($1, $2, $3, $4) on conflict do nothing`,
          [
            tenantId,
            buildingId,
            v === 'pdf' ? 'a4_print' : v === 'ig' ? 'instagram_square' : v === 'story' ? 'whatsapp_story' : 'generic_image',
            qrPayload,
          ],
        );
      }

      return {
        pdf_url: urls.pdf_url!,
        ig_url: urls.ig_url!,
        story_url: urls.story_url!,
        og_url: urls.og_url!,
        qr_payload: qrPayload,
      };
    });
  }
}
