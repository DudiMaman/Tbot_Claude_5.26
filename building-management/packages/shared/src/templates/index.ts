/**
 * Notification templates — Hebrew first.
 * Variables use {{name}} syntax and are substituted by NotificationsModule.
 *
 * WhatsApp templates must be pre-approved in Meta Business Manager; the
 * `meta_template_name` field references the approved template name.
 */

export interface NotificationTemplate {
  key: string;
  channel: 'push' | 'email' | 'sms' | 'whatsapp' | 'in_app';
  locale: 'he' | 'en';
  subject?: string;
  body: string;
  meta_template_name?: string;
  meta_template_lang?: string;
}

export const TEMPLATES: NotificationTemplate[] = [
  // ---- Charge reminders ----
  {
    key: 'charge_due',
    channel: 'whatsapp',
    locale: 'he',
    body: 'שלום {{name}}, חיוב על סך {{amount}} עומד לפירעון ב-{{due_date}}. לתשלום מאובטח: {{pay_url}}',
    meta_template_name: 'charge_reminder_he',
    meta_template_lang: 'he',
  },
  {
    key: 'charge_due',
    channel: 'sms',
    locale: 'he',
    body: 'שלום {{name}}, חיוב {{amount}} ב-{{due_date}}. תשלום: {{pay_url}}',
  },
  {
    key: 'charge_due',
    channel: 'email',
    locale: 'he',
    subject: 'חיוב חודשי - {{building_name}}',
    body: 'שלום {{name}},\n\nחיוב על סך {{amount}} עומד לפירעון ב-{{due_date}}.\n\nלתשלום מאובטח: {{pay_url}}\n\nבברכה,\n{{tenant_name}}',
  },
  // ---- Charge overdue ----
  {
    key: 'charge_overdue',
    channel: 'whatsapp',
    locale: 'he',
    body: 'שלום {{name}}, החיוב על סך {{amount}} מ-{{due_date}} עדיין לא שולם. נא להסדיר בהקדם: {{pay_url}}',
    meta_template_name: 'charge_overdue_he',
    meta_template_lang: 'he',
  },
  {
    key: 'charge_overdue_owner_copy',
    channel: 'whatsapp',
    locale: 'he',
    body: 'שלום {{owner_name}}, חיוב הוועד של דירה {{unit}} ({{building_name}}) באיחור. השוכר {{renter_name}} טרם שילם.',
    meta_template_name: 'charge_overdue_owner_copy_he',
    meta_template_lang: 'he',
  },
  // ---- Welcome ----
  {
    key: 'welcome',
    channel: 'whatsapp',
    locale: 'he',
    body: 'ברוכים הבאים ל-{{tenant_name}}! האפליקציה שלכם מוכנה: {{app_url}}',
    meta_template_name: 'welcome_he',
    meta_template_lang: 'he',
  },
  // ---- Ticket update ----
  {
    key: 'ticket_update',
    channel: 'push',
    locale: 'he',
    subject: 'עדכון בפנייה #{{ticket_id}}',
    body: 'הפנייה "{{title}}" עברה לסטטוס: {{status}}',
  },
  // ---- Bounced check ----
  {
    key: 'check_bounced',
    channel: 'whatsapp',
    locale: 'he',
    body: 'שלום {{name}}, הצ׳ק על סך {{amount}} חזר. סיבה: {{reason}}. נא תשלום חלופי עד {{deadline}}: {{pay_url}}',
    meta_template_name: 'check_bounced_he',
    meta_template_lang: 'he',
  },
  // ---- Invoice issued ----
  {
    key: 'invoice_issued',
    channel: 'whatsapp',
    locale: 'he',
    body: 'הופקה עבורכם {{doc_type}} {{number}} על סך {{amount}}. לצפייה: {{url}}',
    meta_template_name: 'invoice_issued_he',
    meta_template_lang: 'he',
  },
  {
    key: 'invoice_issued',
    channel: 'email',
    locale: 'he',
    subject: '{{doc_type}} {{number}} מ-{{tenant_name}}',
    body: 'שלום {{name}},\n\nמצורפת {{doc_type}} {{number}} על סך {{amount}}.\n\n{{tenant_name}}',
  },
  // ---- Poll invite ----
  {
    key: 'poll_invite',
    channel: 'whatsapp',
    locale: 'he',
    body: 'הצבעה חדשה בנושא "{{title}}". להצבעה: {{url}}',
    meta_template_name: 'poll_invite_he',
    meta_template_lang: 'he',
  },
  // ---- OTP ----
  {
    key: 'otp',
    channel: 'whatsapp',
    locale: 'he',
    body: 'קוד האימות שלכם: {{code}}',
    meta_template_name: 'otp_he',
    meta_template_lang: 'he',
  },
  // ---- Document expiring ----
  {
    key: 'document_expiring',
    channel: 'email',
    locale: 'he',
    subject: 'מסמך עומד לפוג: {{title}}',
    body: 'המסמך "{{title}}" בקטגוריה {{category}} פג ב-{{expires_at}}. נא לחדש.',
  },
];

export function findTemplate(
  key: string,
  channel: NotificationTemplate['channel'],
  locale: NotificationTemplate['locale'] = 'he',
): NotificationTemplate | undefined {
  return TEMPLATES.find((t) => t.key === key && t.channel === channel && t.locale === locale);
}

/** Trivial mustache-style interpolation. No HTML escaping; consumers handle. */
export function renderTemplate(body: string, vars: Record<string, string | number>): string {
  return body.replace(/\{\{(\w+)\}\}/g, (_, k) => {
    const v = vars[k];
    return v === undefined || v === null ? '' : String(v);
  });
}
