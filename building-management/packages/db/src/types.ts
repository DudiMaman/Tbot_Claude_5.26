/**
 * Hand-written TypeScript types matching the Postgres schema.
 * In production, prefer auto-generated types via:
 *   - Prisma: `pnpm --filter @bm/db prisma:generate`
 *   - Supabase: `supabase gen types typescript --local`
 *
 * These hand types are used for compile-time correctness until a real
 * DB is provisioned. They mirror the columns in the migrations 0001..0011.
 */

export type UUID = string;
export type Money = string; // numeric(12,2) — use string to avoid float issues
export type ISODate = string;
export type ISODateTime = string;

// ---- Enums ----

export type TenantPlan = 'trial' | 'starter' | 'pro' | 'enterprise';
export type TenantStatus = 'active' | 'suspended' | 'cancelled';
export type UserRole = 'mgmt_admin' | 'mgmt_member' | 'maintenance' | 'resident';
export type ApartmentRole = 'owner' | 'renter' | 'family_member' | 'authorized_contact';
export type ApartmentOccupancy = 'vacant' | 'owner_occupied' | 'rented' | 'mixed';
export type AssignmentStatus = 'active' | 'pending' | 'ended' | 'superseded';
export type BillPayerRule =
  | 'current_bill_payer'
  | 'specific_person_id'
  | 'owner'
  | 'primary_occupant';
export type VaadResponsibility = 'renter_pays' | 'owner_pays' | 'split';
export type RentalStatus = 'draft' | 'active' | 'ended' | 'terminated';
export type ClaimStatus = 'pending' | 'approved' | 'rejected';

export type ChargeStatus =
  | 'pending'
  | 'paid'
  | 'partial'
  | 'overdue'
  | 'cancelled'
  | 'refunded'
  | 'unbilled_no_payer';
export type PaymentStatus = 'pending' | 'captured' | 'failed' | 'refunded';
export type PaymentMethodType = 'card' | 'cash' | 'check' | 'wire' | 'other';
export type ScheduleCadence = 'one_off' | 'monthly' | 'quarterly' | 'annual';
export type ScheduleStatus = 'active' | 'paused' | 'ended';
export type CardBrand =
  | 'visa'
  | 'mastercard'
  | 'amex'
  | 'isracard'
  | 'leumicard'
  | 'diners'
  | 'unknown';

export type InvoiceType = 'tax_invoice' | 'receipt' | 'tax_invoice_receipt' | 'credit_note';
export type InvoiceStatus = 'draft' | 'issued' | 'sent' | 'cancelled' | 'replaced';
export type ItaClearanceStatus = 'not_required' | 'requested' | 'approved' | 'rejected';

export type CheckStatus =
  | 'received'
  | 'scheduled'
  | 'deposited'
  | 'cleared'
  | 'bounced'
  | 'replaced'
  | 'voided';
export type BatchStatus = 'draft' | 'deposited' | 'partially_cleared' | 'fully_cleared';
export type BounceReason =
  | 'insufficient_funds'
  | 'account_closed'
  | 'stop_payment'
  | 'signature_mismatch'
  | 'wrong_date'
  | 'amount_mismatch'
  | 'other';
export type BounceRecoveryStatus =
  | 'open'
  | 'replacement_received'
  | 'paid_other'
  | 'legal_handover'
  | 'written_off';

export type DocumentCategory =
  | 'insurance'
  | 'contract'
  | 'minutes'
  | 'permit'
  | 'blueprint'
  | 'certificate'
  | 'financial_report'
  | 'rental_contract'
  | 'vendor_invoice'
  | 'meeting_protocol'
  | 'bylaws'
  | 'other';
export type DocumentVisibility =
  | 'mgmt_only'
  | 'owners'
  | 'bill_payers'
  | 'all_occupants'
  | 'building_public';
export type DocumentStatus = 'active' | 'archived' | 'superseded';

export type TicketIntakeChannel = 'app' | 'whatsapp' | 'bot' | 'phone' | 'walkin' | 'email';
export type TicketStatus =
  | 'new'
  | 'triaged'
  | 'assigned'
  | 'in_progress'
  | 'pending_parts'
  | 'resolved'
  | 'closed';
export type TicketCategory =
  | 'plumbing'
  | 'electrical'
  | 'elevator'
  | 'cleaning'
  | 'security'
  | 'hvac'
  | 'common_area'
  | 'access'
  | 'billing'
  | 'other';
export type TicketPriority = 'low' | 'med' | 'high' | 'urgent';

export type TaskStatus = 'todo' | 'in_progress' | 'blocked' | 'done' | 'cancelled';
export type TaskSource = 'planned' | 'ticket' | 'adhoc';

export type ConvChannel = 'in_app' | 'whatsapp' | 'web_widget';
export type ConvStatus = 'open' | 'pending_bot' | 'pending_human' | 'closed';
export type MessageDirection = 'in' | 'out';
export type MessageSenderType = 'resident' | 'mgmt' | 'bot' | 'system';
export type MessageStatus = 'queued' | 'sent' | 'delivered' | 'read' | 'failed';
export type NotificationChannel = 'push' | 'email' | 'sms' | 'whatsapp' | 'in_app';
export type NotificationStatus = 'queued' | 'sent' | 'failed' | 'read';

export type GateKind = 'parking' | 'pedestrian' | 'service';
export type GateProvider = 'http_webhook' | 'mqtt' | 'sesame' | 'custom';
export type AccessAction = 'open' | 'deny';

// ---- Rows ----

export interface Tenant {
  id: UUID;
  name: string;
  legal_name: string | null;
  vat_id: string | null;
  billing_email: string;
  plan: TenantPlan;
  trial_ends_at: ISODateTime | null;
  locale: string;
  timezone: string;
  branding: Record<string, unknown>;
  features: Record<string, unknown>;
  status: TenantStatus;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface Building {
  id: UUID;
  tenant_id: UUID;
  name: string;
  address_line: string;
  city: string;
  postal_code: string | null;
  geo: unknown | null;
  num_floors: number | null;
  num_apartments: number | null;
  year_built: number | null;
  bank_account_iban: string | null;
  claim_secret: string;
  notes: string | null;
  settings: Record<string, unknown>;
  notification_policy: Record<string, unknown>;
  created_at: ISODateTime;
  updated_at: ISODateTime;
  deleted_at: ISODateTime | null;
}

export interface Apartment {
  id: UUID;
  tenant_id: UUID;
  building_id: UUID;
  unit_number: string;
  floor: number | null;
  size_sqm: Money | null;
  num_rooms: string | null;
  occupancy_status: ApartmentOccupancy;
  monthly_dues_amount: Money | null;
  notification_policy: Record<string, unknown>;
  notes: string | null;
  created_at: ISODateTime;
  updated_at: ISODateTime;
  deleted_at: ISODateTime | null;
}

export interface Person {
  id: UUID;
  tenant_id: UUID;
  full_name: string;
  id_number_encrypted: Buffer | null;
  phone_e164: string | null;
  email: string | null;
  language: string;
  push_token: string | null;
  whatsapp_opt_in: boolean;
  claim_status: ClaimStatus;
  claim_method: string | null;
  supabase_user_id: UUID | null;
  notification_prefs: Record<string, unknown>;
  created_at: ISODateTime;
  updated_at: ISODateTime;
  deleted_at: ISODateTime | null;
}

export interface ManagementUser {
  id: UUID;
  tenant_id: UUID;
  full_name: string;
  email: string;
  phone_e164: string | null;
  role: 'mgmt_admin' | 'mgmt_member';
  permissions: Record<string, unknown>;
  supabase_user_id: UUID | null;
  last_login_at: ISODateTime | null;
  created_at: ISODateTime;
  updated_at: ISODateTime;
  deleted_at: ISODateTime | null;
}

export interface MaintenanceWorker {
  id: UUID;
  tenant_id: UUID;
  full_name: string;
  phone_e164: string;
  email: string | null;
  skills: string[];
  employment_type: string;
  hourly_rate: Money | null;
  supabase_user_id: UUID | null;
  status: string;
  created_at: ISODateTime;
  updated_at: ISODateTime;
  deleted_at: ISODateTime | null;
}

export interface ApartmentAssignment {
  id: UUID;
  tenant_id: UUID;
  apartment_id: UUID;
  person_id: UUID;
  role: ApartmentRole;
  is_primary: boolean;
  is_occupant: boolean;
  is_bill_payer: boolean;
  share_pct: string | null;
  valid_from: ISODate;
  valid_to: ISODate | null;
  rental_contract_id: UUID | null;
  notes: string | null;
  status: AssignmentStatus;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface RentalContract {
  id: UUID;
  tenant_id: UUID;
  apartment_id: UUID;
  owner_person_id: UUID;
  renter_person_id: UUID;
  start_date: ISODate;
  end_date: ISODate | null;
  monthly_rent: Money | null;
  vaad_responsibility: VaadResponsibility;
  split_renter_pct: string | null;
  contract_file_id: UUID | null;
  status: RentalStatus;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface ChargeSchedule {
  id: UUID;
  tenant_id: UUID;
  building_id: UUID;
  apartment_id: UUID | null;
  name: string;
  description: string | null;
  amount: Money;
  currency: string;
  cadence: ScheduleCadence;
  day_of_month: number | null;
  start_date: ISODate;
  end_date: ISODate | null;
  installments_allowed: number;
  bill_payer_rule: BillPayerRule;
  bill_payer_person_id: UUID | null;
  status: ScheduleStatus;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface Charge {
  id: UUID;
  tenant_id: UUID;
  building_id: UUID;
  apartment_id: UUID;
  billed_to_person_id: UUID | null;
  schedule_id: UUID | null;
  description: string | null;
  amount: Money;
  currency: string;
  due_date: ISODate;
  status: ChargeStatus;
  invoice_id: UUID | null;
  invoice_number: string | null;
  vat_amount: Money | null;
  paid_amount: Money;
  last_reminder_at: ISODateTime | null;
  dunning_stage: number;
  metadata: Record<string, unknown>;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface Payment {
  id: UUID;
  tenant_id: UUID;
  charge_id: UUID;
  paid_by_person_id: UUID | null;
  payment_method_id: UUID | null;
  method: PaymentMethodType;
  amount: Money;
  currency: string;
  status: PaymentStatus;
  tranzila_token_id: string | null;
  tranzila_txn_id: string | null;
  last4: string | null;
  brand: CardBrand | null;
  installments: number;
  captured_at: ISODateTime | null;
  failure_reason: string | null;
  raw_provider_json: Record<string, unknown> | null;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface PaymentMethod {
  id: UUID;
  tenant_id: UUID;
  owner_person_id: UUID;
  type: PaymentMethodType;
  tranzila_token: string | null;
  brand: CardBrand;
  last4: string | null;
  expiry_month: number | null;
  expiry_year: number | null;
  is_default: boolean;
  status: string;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface InvoiceSeries {
  id: UUID;
  tenant_id: UUID;
  building_id: UUID | null;
  document_type: InvoiceType;
  name: string;
  prefix: string;
  next_serial: number;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface Invoice {
  id: UUID;
  tenant_id: UUID;
  building_id: UUID | null;
  apartment_id: UUID | null;
  series_id: UUID;
  type: InvoiceType;
  serial_number: number | null;
  status: InvoiceStatus;
  issued_at: ISODateTime | null;
  issued_by_user_id: UUID | null;
  customer_person_id: UUID | null;
  customer_name_snapshot: string | null;
  customer_address_snapshot: string | null;
  customer_vat_id_snapshot: string | null;
  description: string | null;
  currency: string;
  subtotal: Money;
  vat_rate_pct: string;
  vat_amount: Money;
  total: Money;
  related_charge_ids: UUID[];
  related_payment_ids: UUID[];
  credit_note_for_invoice_id: UUID | null;
  pdf_file_id: UUID | null;
  ita_allocation_number: string | null;
  ita_clearance_status: ItaClearanceStatus;
  ita_clearance_payload: Record<string, unknown> | null;
  delivered_channels: Record<string, unknown>;
  content_hash: string | null;
  metadata: Record<string, unknown>;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface Check {
  id: UUID;
  tenant_id: UUID;
  building_id: UUID;
  apartment_id: UUID | null;
  payer_person_id: UUID | null;
  bank_code: string;
  branch_code: string;
  account_number: string;
  check_number: string;
  amount: Money;
  currency: string;
  issue_date: ISODate;
  presented_date: ISODate;
  due_date: ISODate;
  scan_file_id: UUID | null;
  status: CheckStatus;
  deposit_batch_id: UUID | null;
  related_charge_ids: UUID[];
  received_by_user_id: UUID | null;
  notes: string | null;
  metadata: Record<string, unknown>;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface CheckBatch {
  id: UUID;
  tenant_id: UUID;
  building_id: UUID;
  bank_account_iban: string;
  deposit_date: ISODate;
  total_amount: Money;
  status: BatchStatus;
  bank_deposit_slip_file_id: UUID | null;
  bank_reference: string | null;
  notes: string | null;
  created_by_user_id: UUID | null;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface BouncedCheck {
  id: UUID;
  tenant_id: UUID;
  original_check_id: UUID;
  bounce_reason: BounceReason;
  bounce_reason_text: string | null;
  bounced_on: ISODate;
  bank_fee_amount: Money;
  recharge_fee_amount: Money;
  recovery_status: BounceRecoveryStatus;
  replacement_check_id: UUID | null;
  replacement_payment_id: UUID | null;
  legal_handover_at: ISODateTime | null;
  resolution_notes: string | null;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface Document {
  id: UUID;
  tenant_id: UUID;
  building_id: UUID;
  apartment_id: UUID | null;
  title: string;
  category: DocumentCategory;
  description: string | null;
  expires_at: ISODate | null;
  reminder_lead_days: number;
  tags: string[];
  current_version_id: UUID | null;
  visibility: DocumentVisibility;
  status: DocumentStatus;
  metadata: Record<string, unknown>;
  created_at: ISODateTime;
  updated_at: ISODateTime;
  deleted_at: ISODateTime | null;
}

export interface DocumentVersion {
  id: UUID;
  tenant_id: UUID;
  document_id: UUID;
  version_number: number;
  file_id: UUID;
  uploaded_by_user_id: UUID | null;
  upload_notes: string | null;
  size_bytes: number;
  mime: string | null;
  sha256: string | null;
  ocr_text: string | null;
  ai_summary: string | null;
  ai_metadata: Record<string, unknown> | null;
  created_at: ISODateTime;
}

export interface ServiceTicket {
  id: UUID;
  tenant_id: UUID;
  building_id: UUID;
  apartment_id: UUID | null;
  opened_by_person_id: UUID | null;
  intake_channel: TicketIntakeChannel;
  title: string;
  description: string | null;
  category: TicketCategory;
  priority: TicketPriority;
  photos: string[];
  videos: string[];
  status: TicketStatus;
  assigned_task_id: UUID | null;
  sla_due_at: ISODateTime | null;
  satisfaction_rating: number | null;
  resolution_note: string | null;
  opened_at: ISODateTime;
  resolved_at: ISODateTime | null;
  closed_at: ISODateTime | null;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface Task {
  id: UUID;
  tenant_id: UUID;
  building_id: UUID;
  apartment_id: UUID | null;
  source: TaskSource;
  source_ticket_id: UUID | null;
  title: string;
  description_md: string | null;
  category: TicketCategory;
  priority: TicketPriority;
  assigned_worker_id: UUID | null;
  scheduled_at: ISODateTime | null;
  sla_due_at: ISODateTime | null;
  started_at: ISODateTime | null;
  completed_at: ISODateTime | null;
  status: TaskStatus;
  checklist: unknown[];
  time_spent_minutes: number;
  cost_amount: Money | null;
  customer_visible: boolean;
  metadata: Record<string, unknown>;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface Vendor {
  id: UUID;
  tenant_id: UUID;
  name: string;
  contact_name: string | null;
  phone: string | null;
  email: string | null;
  vat_id: string | null;
  iban: string | null;
  services: string[];
  rating: string | null;
  notes: string | null;
  status: 'active' | 'inactive' | 'blocked';
  created_at: ISODateTime;
  updated_at: ISODateTime;
  deleted_at: ISODateTime | null;
}

export interface BulletinPost {
  id: UUID;
  tenant_id: UUID;
  building_id: UUID;
  author_user_id: UUID | null;
  title: string;
  body_md: string;
  attachments: unknown[];
  pinned: boolean;
  pinned_until: ISODateTime | null;
  expires_at: ISODateTime | null;
  audience: Record<string, unknown>;
  reactions_enabled: boolean;
  comments_enabled: boolean;
  published_at: ISODateTime | null;
  status: 'draft' | 'published' | 'archived';
  metadata: Record<string, unknown>;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface Poll {
  id: UUID;
  tenant_id: UUID;
  building_id: UUID;
  author_user_id: UUID | null;
  title: string;
  description: string | null;
  type: 'single' | 'multi' | 'ranked';
  options: unknown[];
  eligibility: 'per_apartment' | 'per_resident' | 'owner_only' | 'bill_payer_only';
  anonymous: boolean;
  opens_at: ISODateTime;
  closes_at: ISODateTime;
  requires_signature: boolean;
  status: 'draft' | 'open' | 'closed' | 'archived';
  metadata: Record<string, unknown>;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface Vote {
  id: UUID;
  tenant_id: UUID;
  poll_id: UUID;
  person_id: UUID | null;
  person_id_hash: string | null;
  apartment_id: UUID;
  choice: unknown;
  signature_blob: string | null;
  ip_hash: string | null;
  user_agent: string | null;
  voted_at: ISODateTime;
}

export interface Conversation {
  id: UUID;
  tenant_id: UUID;
  building_id: UUID | null;
  person_id: UUID | null;
  apartment_id: UUID | null;
  channel: ConvChannel;
  status: ConvStatus;
  assigned_user_id: UUID | null;
  whatsapp_phone_e164: string | null;
  last_message_at: ISODateTime | null;
  metadata: Record<string, unknown>;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface Message {
  id: UUID;
  tenant_id: UUID;
  conversation_id: UUID;
  direction: MessageDirection;
  sender_type: MessageSenderType;
  sender_user_id: UUID | null;
  sender_person_id: UUID | null;
  body: string | null;
  attachments: unknown[];
  whatsapp_message_id: string | null;
  status: MessageStatus;
  created_at: ISODateTime;
  delivered_at: ISODateTime | null;
  read_at: ISODateTime | null;
}

export interface Notification {
  id: UUID;
  tenant_id: UUID;
  recipient_person_id: UUID | null;
  recipient_user_id: UUID | null;
  channel: NotificationChannel;
  template_key: string;
  payload: Record<string, unknown>;
  status: NotificationStatus;
  provider_message_id: string | null;
  dedupe_key: string | null;
  scheduled_for: ISODateTime;
  sent_at: ISODateTime | null;
  read_at: ISODateTime | null;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface AccessGate {
  id: UUID;
  tenant_id: UUID;
  building_id: UUID;
  name: string;
  kind: GateKind;
  provider: GateProvider;
  config: Record<string, unknown>;
  status: string;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface AddonProduct {
  id: UUID;
  tenant_id: UUID;
  sku: string;
  name: string;
  description: string | null;
  price: Money;
  currency: string;
  vat_inclusive: boolean;
  availability_buildings: UUID[];
  inventory: number | null;
  commission_pct: string;
  image_file_id: UUID | null;
  status: 'active' | 'inactive' | 'archived';
  metadata: Record<string, unknown>;
  created_at: ISODateTime;
  updated_at: ISODateTime;
  deleted_at: ISODateTime | null;
}

export interface AddonOrder {
  id: UUID;
  tenant_id: UUID;
  product_id: UUID;
  ordered_by_person_id: UUID;
  building_id: UUID | null;
  apartment_id: UUID | null;
  qty: number;
  total: Money;
  payment_id: UUID | null;
  fulfillment_status: 'pending' | 'in_progress' | 'delivered' | 'cancelled';
  notes: string | null;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}
