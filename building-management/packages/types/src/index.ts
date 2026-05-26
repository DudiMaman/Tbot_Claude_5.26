/**
 * Shared API contract types — generated from OpenAPI spec in production.
 * For now hand-written to keep the workspace compiling.
 */

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface ApiResponse<T> {
  data: T;
  meta?: { total?: number; page?: number; per_page?: number };
}

export interface JwtClaims {
  sub: string;
  tenant_id: string;
  role: 'mgmt_admin' | 'mgmt_member' | 'maintenance' | 'resident';
  person_id?: string;
  building_ids?: string[];
  apartment_ids?: string[];
  permissions?: string[];
}

export interface FlyerVariants {
  pdf_url: string;
  ig_url: string;
  story_url: string;
  og_url: string;
}

export interface BillPayerResolutionResult {
  apartment_id: string;
  resolved_person_id: string | null;
  rule_used: string;
  fallback_used: boolean;
  reason_no_payer?: string;
}

export interface DryRunCycle {
  schedule_id: string;
  cycle_date: string;
  charges: Array<{
    apartment_id: string;
    apartment_unit_number: string;
    billed_to_person_id: string | null;
    billed_to_name: string | null;
    amount: number;
    status: 'will_be_billed' | 'unresolved_payer';
  }>;
  totals: { count: number; unresolved: number; amount: number };
}
