export const VAT_RATE_PCT = 17;
export const DEFAULT_CURRENCY = 'ILS';
export const DEFAULT_LOCALE = 'he-IL';
export const DEFAULT_TIMEZONE = 'Asia/Jerusalem';
export const ITA_E_INVOICE_THRESHOLD_ILS = 25_000;
export const MAX_INSTALLMENTS = 12;

export const APP_DOMAINS = {
  marketing: 'building-management.co.il',
  admin: 'app.building-management.co.il',
  api: 'api.building-management.co.il',
} as const;

export const SUPPORTED_LANGUAGES = ['he', 'en', 'ru', 'ar'] as const;
export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number];

export const TICKET_CATEGORIES = [
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
] as const;

export const TICKET_CATEGORY_LABELS_HE: Record<string, string> = {
  plumbing: 'אינסטלציה',
  electrical: 'חשמל',
  elevator: 'מעלית',
  cleaning: 'ניקיון',
  security: 'אבטחה',
  hvac: 'מיזוג אוויר',
  common_area: 'שטחים משותפים',
  access: 'גישה / שערים',
  billing: 'חיוב / תשלום',
  other: 'אחר',
};

export const DUNNING_STAGES = [
  { stage: 0, day: 0, action: 'create_charge' },
  { stage: 1, day: 0, action: 'reminder_app' },
  { stage: 2, day: 3, action: 'reminder_email' },
  { stage: 3, day: 7, action: 'reminder_sms_whatsapp' },
  { stage: 4, day: 14, action: 'notify_owner' },
  { stage: 5, day: 21, action: 'final_notice' },
  { stage: 6, day: 30, action: 'legal_review' },
] as const;

export const NOTIFICATION_DND_HOURS = { start: 21, end: 7 } as const;

export const DEFAULT_NOTIFICATION_POLICY = {
  charge_due: ['bill_payer'],
  charge_overdue: ['bill_payer', 'owner'],
  ticket_update: ['opener', 'all_occupants'],
  bulletin: ['all_occupants', 'owner_if_absentee'],
  maintenance_entry: ['all_occupants', 'owner'],
  poll_open: ['eligible_voters_per_rule'],
} as const;
