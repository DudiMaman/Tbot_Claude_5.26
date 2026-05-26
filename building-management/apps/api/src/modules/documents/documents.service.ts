/**
 * DocumentsService — building document vault per SPEC §39.
 *
 * Upload flow: existing File row referenced by file_id is attached as
 * version 1 (or N+1) of the Document. AI summary + OCR are async jobs.
 */
import { Injectable, Logger, NotFoundException } from '@nestjs/common';
import { DbService } from '../../db/db.service';
import type { UploadDocument } from '@bm/shared';
import type { Document, DocumentVersion } from '@bm/db';

@Injectable()
export class DocumentsService {
  private readonly logger = new Logger(DocumentsService.name);
  constructor(private readonly db: DbService) {}

  async upload(
    tenantId: string,
    actorUserId: string,
    input: UploadDocument,
  ): Promise<{ document: Document; version: DocumentVersion }> {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      // Insert document
      const docRes = await c.query<Document>(
        `insert into documents
          (tenant_id, building_id, apartment_id, title, category, description,
           expires_at, reminder_lead_days, tags, visibility)
         values ($1, $2, $3, $4, $5, $6, $7, $8, $9::text[], $10)
         returning *`,
        [
          tenantId,
          input.building_id,
          input.apartment_id ?? null,
          input.title,
          input.category,
          input.description ?? null,
          input.expires_at ?? null,
          input.reminder_lead_days,
          input.tags,
          input.visibility,
        ],
      );
      const doc = docRes.rows[0]!;

      // Fetch file metadata
      const fileRes = await c.query<{ size_bytes: number; mime: string | null; sha256: string | null }>(
        `select size_bytes, mime, sha256 from files where id = $1`,
        [input.file_id],
      );
      if (fileRes.rows.length === 0) throw new NotFoundException('File not found');

      // Version 1
      const verRes = await c.query<DocumentVersion>(
        `insert into document_versions
          (tenant_id, document_id, version_number, file_id, uploaded_by_user_id, size_bytes, mime, sha256)
         values ($1, $2, 1, $3, $4, $5, $6, $7)
         returning *`,
        [
          tenantId,
          doc.id,
          input.file_id,
          actorUserId,
          fileRes.rows[0]!.size_bytes,
          fileRes.rows[0]!.mime,
          fileRes.rows[0]!.sha256,
        ],
      );

      // current_version_id auto-set by trigger
      return { document: doc, version: verRes.rows[0]! };
    });
  }

  async addVersion(
    tenantId: string,
    actorUserId: string,
    docId: string,
    fileId: string,
    notes?: string,
  ): Promise<DocumentVersion> {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const next = await c.query<{ next: number }>(
        `select coalesce(max(version_number), 0) + 1 as next from document_versions where document_id = $1`,
        [docId],
      );
      const fileRes = await c.query<{ size_bytes: number; mime: string | null; sha256: string | null }>(
        `select size_bytes, mime, sha256 from files where id = $1`,
        [fileId],
      );
      const { rows } = await c.query<DocumentVersion>(
        `insert into document_versions
          (tenant_id, document_id, version_number, file_id, uploaded_by_user_id, upload_notes, size_bytes, mime, sha256)
         values ($1, $2, $3, $4, $5, $6, $7, $8, $9) returning *`,
        [
          tenantId,
          docId,
          next.rows[0]!.next,
          fileId,
          actorUserId,
          notes ?? null,
          fileRes.rows[0]?.size_bytes ?? 0,
          fileRes.rows[0]?.mime ?? null,
          fileRes.rows[0]?.sha256 ?? null,
        ],
      );
      return rows[0]!;
    });
  }

  async list(tenantId: string, buildingId: string, category?: string) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const conds = ['building_id = $1', `status = 'active'`];
      const params: any[] = [buildingId];
      if (category) {
        params.push(category);
        conds.push(`category = $${params.length}`);
      }
      const { rows } = await c.query(
        `select d.*, dv.size_bytes, dv.mime
         from documents d
         left join document_versions dv on dv.id = d.current_version_id
         where ${conds.join(' and ')}
         order by d.created_at desc`,
        params,
      );
      return rows;
    });
  }

  async expiringSoon(tenantId: string, days: number = 30) {
    return this.db.withTenantContext({ tenant_id: tenantId, role: 'mgmt_admin' }, async (c) => {
      const { rows } = await c.query(
        `select * from documents
         where status = 'active'
           and expires_at is not null
           and expires_at - (reminder_lead_days || ' days')::interval <= current_date
           and expires_at >= current_date
         order by expires_at`,
      );
      return rows;
    });
  }
}
