/**
 * FilesService — Supabase Storage integration.
 *
 * For local dev / test we expose signed-URL placeholders. Real impl uses
 * supabase-js to upload (server-side, service-role key) and createSignedUrl.
 */
import { Injectable, Logger } from '@nestjs/common';
import { DbService } from '../../db/db.service';

@Injectable()
export class FilesService {
  private readonly logger = new Logger(FilesService.name);

  constructor(private readonly db: DbService) {}

  /**
   * Create a File row + return an upload URL.
   * Frontend then PUTs the binary directly to that URL.
   */
  async createUploadIntent(
    tenantId: string,
    ownerUserId: string | null,
    ownerPersonId: string | null,
    bucket: string,
    path: string,
    mime: string,
    sizeBytes: number,
    piiTag: 'none' | 'pii' | 'financial' | 'sensitive' = 'none',
  ) {
    const { rows } = await this.db.query<{ id: string }>(
      `insert into files (tenant_id, owner_user_id, owner_person_id, bucket, path, mime, size_bytes, pii_tag)
       values ($1, $2, $3, $4, $5, $6, $7, $8) returning id`,
      [tenantId, ownerUserId, ownerPersonId, bucket, path, mime, sizeBytes, piiTag],
    );
    const fileId = rows[0]!.id;
    const uploadUrl = `https://storage.example.com/${bucket}/${path}?intent=${fileId}`;
    return { file_id: fileId, upload_url: uploadUrl };
  }

  async getSignedUrl(fileId: string, expiresIn: number = 3600): Promise<string | null> {
    const { rows } = await this.db.query<{ bucket: string; path: string }>(
      `select bucket, path from files where id = $1 and deleted_at is null`,
      [fileId],
    );
    if (rows.length === 0) return null;
    const r = rows[0]!;
    return `https://storage.example.com/${r.bucket}/${r.path}?expires=${Date.now() + expiresIn * 1000}`;
  }
}
