/**
 * Zod schemas for runtime validation at API boundaries.
 * All requests/responses funnel through these.
 */

import { z } from 'zod';

// ---- Reusable atoms ----

export const UUID = z.string().uuid();
export const ISODate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);
export const ISODateTime = z.string().datetime({ offset: true });
export const Money = z.string().regex(/^\d+(\.\d{1,2})?$/);
export const E164Phone = z.string().regex(/^\+972\d{8,9}$/);
export const ILS = z.literal('ILS');

// ---- Enums ----

export const ApartmentRoleSchema = z.enum(['owner', 'renter', 'family_member', 'authorized_contact']);
export const VaadResponsibilitySchema = z.enum(['renter_pays', 'owner_pays', 'split']);
export const BillPayerRuleSchema = z.enum([
  'current_bill_payer',
  'specific_person_id',
  'owner',
  'primary_occupant',
]);
export const ScheduleCadenceSchema = z.enum(['one_off', 'monthly', 'quarterly', 'annual']);
export const TicketCategorySchema = z.enum([
  'plumbing',
  'electrical',
  'elevator',
  'cleaning',
  'security',
  'hvac',
  'common_area',
  'access',
  'billing',
  'other',
]);
export const TicketPrioritySchema = z.enum(['low', 'med', 'high', 'urgent']);

// ---- Tenants ----

export const CreateTenantSchema = z.object({
  name: z.string().min(2).max(120),
  legal_name: z.string().optional(),
  vat_id: z.string().optional(),
  billing_email: z.string().email(),
  phone: E164Phone.optional(),
});

// ---- Buildings ----

export const CreateBuildingSchema = z.object({
  name: z.string().min(2).max(120),
  address_line: z.string().min(2),
  city: z.string().min(1),
  postal_code: z.string().optional(),
  geo_lat: z.number().min(-90).max(90).optional(),
  geo_lng: z.number().min(-180).max(180).optional(),
  num_floors: z.number().int().positive().optional(),
  num_apartments: z.number().int().positive().optional(),
  year_built: z.number().int().min(1800).max(new Date().getFullYear() + 5).optional(),
  bank_account_iban: z.string().optional(),
});

// ---- Apartments ----

export const CreateApartmentSchema = z.object({
  building_id: UUID,
  unit_number: z.string().min(1).max(20),
  floor: z.number().int().optional(),
  size_sqm: z.number().positive().optional(),
  num_rooms: z.number().positive().optional(),
  monthly_dues_amount: z.number().nonnegative().optional(),
});

export const BulkCreateApartmentsSchema = z.object({
  building_id: UUID,
  apartments: z.array(CreateApartmentSchema.omit({ building_id: true })).min(1).max(500),
});

// ---- People ----

export const CreatePersonSchema = z.object({
  full_name: z.string().min(2).max(120),
  phone_e164: E164Phone.optional(),
  email: z.string().email().optional(),
  language: z.enum(['he', 'en', 'ru', 'ar']).default('he'),
});

// ---- Apartment Assignments ----

export const CreateAssignmentSchema = z
  .object({
    apartment_id: UUID,
    person_id: UUID,
    role: ApartmentRoleSchema,
    is_primary: z.boolean().default(false),
    is_occupant: z.boolean().default(false),
    is_bill_payer: z.boolean().default(false),
    share_pct: z.number().min(0).max(100).optional(),
    valid_from: ISODate.optional(),
    valid_to: ISODate.optional(),
  })
  .refine(
    (v) => v.role !== 'renter' || v.is_occupant === true,
    { message: 'renter must be occupant', path: ['is_occupant'] },
  );

// ---- Rental Contracts ----

export const CreateRentalContractSchema = z
  .object({
    apartment_id: UUID,
    owner_person_id: UUID,
    renter_person_id: UUID,
    start_date: ISODate,
    end_date: ISODate.optional(),
    monthly_rent: z.number().positive().optional(),
    vaad_responsibility: VaadResponsibilitySchema.default('renter_pays'),
    split_renter_pct: z.number().min(0).max(100).optional(),
    contract_file_id: UUID.optional(),
  })
  .refine((v) => v.owner_person_id !== v.renter_person_id, {
    message: 'owner and renter must be different',
  })
  .refine(
    (v) => v.vaad_responsibility !== 'split' || (v.split_renter_pct !== undefined),
    { message: 'split_renter_pct required when vaad_responsibility=split' },
  );

// ---- Charge schedules ----

export const CreateChargeScheduleSchema = z.object({
  building_id: UUID,
  apartment_id: UUID.optional(),
  name: z.string().min(2),
  description: z.string().optional(),
  amount: z.number().positive(),
  currency: ILS.default('ILS'),
  cadence: ScheduleCadenceSchema,
  day_of_month: z.number().int().min(1).max(31).optional(),
  start_date: ISODate,
  end_date: ISODate.optional(),
  installments_allowed: z.number().int().min(1).max(12).default(1),
  bill_payer_rule: BillPayerRuleSchema.default('current_bill_payer'),
  bill_payer_person_id: UUID.optional(),
});

// ---- Tickets ----

export const CreateTicketSchema = z.object({
  building_id: UUID,
  apartment_id: UUID.optional(),
  title: z.string().min(2).max(200),
  description: z.string().optional(),
  category: TicketCategorySchema.default('other'),
  priority: TicketPrioritySchema.default('med'),
  photos: z.array(z.string()).default([]),
});

// ---- Payment ----

export const CreatePaymentSchema = z.object({
  charge_id: UUID,
  payment_method_id: UUID.optional(),
  amount: z.number().positive(),
  installments: z.number().int().min(1).max(12).default(1),
});

// ---- Invoices ----

export const IssueInvoiceSchema = z.object({
  series_id: UUID,
  customer_person_id: UUID,
  charge_ids: z.array(UUID).optional(),
  payment_ids: z.array(UUID).optional(),
  description: z.string().optional(),
  line_items: z
    .array(
      z.object({
        description: z.string().min(1),
        quantity: z.number().positive(),
        unit_price: z.number().nonnegative(),
        vat_rate_pct: z.number().min(0).max(100).default(17),
      }),
    )
    .min(1),
});

// ---- Checks ----

export const ReceiveCheckSchema = z.object({
  building_id: UUID,
  apartment_id: UUID.optional(),
  payer_person_id: UUID.optional(),
  bank_code: z.string().regex(/^\d{2,3}$/),
  branch_code: z.string().regex(/^\d{2,4}$/),
  account_number: z.string().regex(/^\d{5,12}$/),
  check_number: z.string().min(1),
  amount: z.number().positive(),
  issue_date: ISODate,
  due_date: ISODate,
  scan_file_id: UUID.optional(),
  related_charge_ids: z.array(UUID).default([]),
});

export const BounceCheckSchema = z.object({
  check_id: UUID,
  bounce_reason: z.enum([
    'insufficient_funds',
    'account_closed',
    'stop_payment',
    'signature_mismatch',
    'wrong_date',
    'amount_mismatch',
    'other',
  ]),
  bounce_reason_text: z.string().optional(),
  bank_fee_amount: z.number().nonnegative().default(0),
  recharge_fee_amount: z.number().nonnegative().default(0),
});

// ---- Documents ----

export const UploadDocumentSchema = z.object({
  building_id: UUID,
  apartment_id: UUID.optional(),
  title: z.string().min(2),
  category: z.enum([
    'insurance',
    'contract',
    'minutes',
    'permit',
    'blueprint',
    'certificate',
    'financial_report',
    'rental_contract',
    'vendor_invoice',
    'meeting_protocol',
    'bylaws',
    'other',
  ]),
  description: z.string().optional(),
  expires_at: ISODate.optional(),
  reminder_lead_days: z.number().int().nonnegative().default(30),
  tags: z.array(z.string()).default([]),
  visibility: z
    .enum(['mgmt_only', 'owners', 'bill_payers', 'all_occupants', 'building_public'])
    .default('mgmt_only'),
  file_id: UUID,
});

// ---- Bulletins ----

export const CreateBulletinSchema = z.object({
  building_id: UUID,
  title: z.string().min(2).max(200),
  body_md: z.string().min(1),
  pinned: z.boolean().default(false),
  pinned_until: ISODateTime.optional(),
  expires_at: ISODateTime.optional(),
  audience: z
    .object({
      type: z.enum(['all', 'apartments', 'role', 'group']),
      apartment_ids: z.array(UUID).optional(),
      role: ApartmentRoleSchema.optional(),
      group_tag: z.string().optional(),
    })
    .default({ type: 'all' }),
  reactions_enabled: z.boolean().default(true),
  comments_enabled: z.boolean().default(false),
});

// ---- Polls ----

export const CreatePollSchema = z.object({
  building_id: UUID,
  title: z.string().min(2),
  description: z.string().optional(),
  type: z.enum(['single', 'multi', 'ranked']).default('single'),
  options: z.array(z.string()).min(2).max(20),
  eligibility: z.enum(['per_apartment', 'per_resident', 'owner_only', 'bill_payer_only']).default('per_apartment'),
  anonymous: z.boolean().default(false),
  opens_at: ISODateTime,
  closes_at: ISODateTime,
  requires_signature: z.boolean().default(false),
});

// ---- Gate ----

export const OpenGateSchema = z.object({
  gate_id: UUID,
  idempotency_key: z.string().optional(),
});

// Export inferred types for client + server
export type CreateTenant = z.infer<typeof CreateTenantSchema>;
export type CreateBuilding = z.infer<typeof CreateBuildingSchema>;
export type CreateApartment = z.infer<typeof CreateApartmentSchema>;
export type CreatePerson = z.infer<typeof CreatePersonSchema>;
export type CreateAssignment = z.infer<typeof CreateAssignmentSchema>;
export type CreateRentalContract = z.infer<typeof CreateRentalContractSchema>;
export type CreateChargeSchedule = z.infer<typeof CreateChargeScheduleSchema>;
export type CreateTicket = z.infer<typeof CreateTicketSchema>;
export type CreatePayment = z.infer<typeof CreatePaymentSchema>;
export type IssueInvoice = z.infer<typeof IssueInvoiceSchema>;
export type ReceiveCheck = z.infer<typeof ReceiveCheckSchema>;
export type BounceCheck = z.infer<typeof BounceCheckSchema>;
export type UploadDocument = z.infer<typeof UploadDocumentSchema>;
export type CreateBulletin = z.infer<typeof CreateBulletinSchema>;
export type CreatePoll = z.infer<typeof CreatePollSchema>;
export type OpenGate = z.infer<typeof OpenGateSchema>;
