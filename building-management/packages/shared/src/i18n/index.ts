/**
 * Hebrew-first i18n keys. The web and mobile apps load these via next-intl /
 * i18next as their default `he` namespace.
 */

export const heCommon = {
  app_name: 'ניהול בניינים',
  yes: 'כן',
  no: 'לא',
  save: 'שמירה',
  cancel: 'ביטול',
  delete: 'מחיקה',
  edit: 'עריכה',
  back: 'חזרה',
  next: 'הבא',
  previous: 'הקודם',
  search: 'חיפוש',
  loading: 'טוען...',
  error: 'אירעה שגיאה',
  retry: 'נסה שוב',
  close: 'סגירה',
  open: 'פתיחה',
  add: 'הוסף',
  remove: 'הסר',
  confirm: 'אישור',
  submit: 'שליחה',
  required: 'שדה חובה',
};

export const heRoles = {
  mgmt_admin: 'מנהל חברת ניהול',
  mgmt_member: 'עובד חברת ניהול',
  maintenance: 'איש אחזקה',
  resident: 'דייר',
  owner: 'בעלים',
  renter: 'שוכר',
  family_member: 'בן/בת משפחה',
  authorized_contact: 'נציג מוסמך',
};

export const heBilling = {
  charge: 'חיוב',
  charges: 'חיובים',
  amount: 'סכום',
  due_date: 'תאריך פירעון',
  installments: 'תשלומים',
  pay_now: 'תשלום עכשיו',
  paid: 'שולם',
  overdue: 'באיחור',
  vat: 'מע"מ',
  total: 'סה"כ',
  receipt: 'קבלה',
  invoice: 'חשבונית',
  tax_invoice: 'חשבונית מס',
  tax_invoice_receipt: 'חשבונית מס/קבלה',
  credit_note: 'חשבונית זיכוי',
  vaad_bayit: 'ועד בית',
  monthly_dues: 'דמי ועד חודשיים',
};

export const heGate = {
  open_parking_gate: 'פתח שער חניה',
  opening: 'פותח...',
  gate_opened: 'השער נפתח',
  gate_failed: 'פתיחת השער נכשלה',
  generate_guest_code: 'הפק קוד אורח',
};

export const heTickets = {
  ticket: 'פנייה',
  tickets: 'פניות',
  new_ticket: 'פנייה חדשה',
  status_new: 'חדשה',
  status_triaged: 'מסווגת',
  status_assigned: 'הוקצתה',
  status_in_progress: 'בטיפול',
  status_pending_parts: 'ממתינה לחלקים',
  status_resolved: 'טופלה',
  status_closed: 'סגורה',
  rate_service: 'דרגו את השירות',
};

export const heChecks = {
  check: 'צ׳ק',
  checks: 'צ׳קים',
  add_check: 'הוסף צ׳ק',
  bounced_check: 'צ׳ק חוזר',
  bounced_checks: 'צ׳קים חוזרים',
  deposit: 'הפקדה',
  deposit_batch: 'אצוות הפקדה',
  check_number: 'מספר צ׳ק',
  bank: 'בנק',
  branch: 'סניף',
  account: 'חשבון',
};

export const heDocs = {
  documents: 'מסמכים',
  document: 'מסמך',
  upload: 'העלאת מסמך',
  category_insurance: 'ביטוח',
  category_contract: 'חוזה',
  category_minutes: 'פרוטוקול',
  category_permit: 'אישור',
  category_blueprint: 'תוכניות',
  category_certificate: 'תעודה',
  category_financial_report: 'דוח כספי',
  category_rental_contract: 'חוזה שכירות',
  category_vendor_invoice: 'חשבונית ספק',
  category_meeting_protocol: 'פרוטוקול אסיפה',
  category_bylaws: 'תקנון בית',
  category_other: 'אחר',
  expires_at: 'תאריך תפוגה',
};

export const heMarketing = {
  hero_h1: 'ניהול מבנים בלי כאב ראש',
  hero_subhead: 'פלטפורמה אחת לחברת הניהול, לדיירים, לבעלי דירות ולאנשי האחזקה',
  cta_trial: 'התחילו ניסיון חינם',
  cta_demo: 'קבעו הדגמה',
};

export const he = {
  common: heCommon,
  roles: heRoles,
  billing: heBilling,
  gate: heGate,
  tickets: heTickets,
  checks: heChecks,
  docs: heDocs,
  marketing: heMarketing,
};

export type Translations = typeof he;
