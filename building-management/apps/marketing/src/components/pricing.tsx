import Link from 'next/link';
import { Check } from 'lucide-react';

const tiers = [
  {
    name: 'Trial',
    price: 'חינם',
    period: '30 יום',
    description: 'כל הפיצ׳רים, בניין אחד, עד 20 דירות',
    cta: 'התחילו עכשיו',
    href: '/signup?plan=trial',
    features: ['בניין יחיד', 'עד 20 דירות', 'כל הפיצ\'רים', 'ללא כרטיס אשראי'],
  },
  {
    name: 'Starter',
    price: '₪399',
    period: 'לחודש',
    description: 'לחברות ניהול קטנות עד 3 בניינים',
    cta: 'בחרו ב-Starter',
    href: '/signup?plan=starter',
    features: ['עד 3 בניינים', 'עד 100 דירות', 'גבייה אוטומטית', 'WhatsApp', 'תמיכה במייל'],
  },
  {
    name: 'Pro',
    price: '₪1,290',
    period: 'לחודש',
    description: 'הבחירה של רוב החברות',
    cta: 'בחרו ב-Pro',
    popular: true,
    href: '/signup?plan=pro',
    features: ['עד 15 בניינים', 'עד 600 דירות', 'בוט AI', 'ייצוא חשבשבת/ריווחית', 'תמיכה בטלפון'],
  },
  {
    name: 'Enterprise',
    price: 'נדבר',
    period: '',
    description: 'לחברות ניהול גדולות',
    cta: 'צרו קשר',
    href: '/contact',
    features: ['ללא הגבלה', 'SLA', 'SSO', 'מנהל לקוח ייעודי', 'אינטגרציות מותאמות'],
  },
];

export function Pricing() {
  return (
    <section id="pricing" className="px-6 py-20">
      <div className="mx-auto max-w-6xl">
        <h2 className="text-center text-4xl font-bold">מחירים שקופים</h2>
        <p className="mx-auto mt-3 max-w-2xl text-center text-slate-600">
          ללא דמי הקמה, ללא התחייבות. שדרגו או בטלו בכל עת.
        </p>
        <div className="mt-12 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          {tiers.map((tier) => (
            <div
              key={tier.name}
              className={`relative rounded-2xl border p-6 ${
                tier.popular
                  ? 'border-primary-500 bg-gradient-to-b from-primary-50 to-white shadow-xl shadow-primary-100'
                  : 'border-slate-200 bg-white'
              }`}
            >
              {tier.popular && (
                <span className="absolute -top-3 right-1/2 inline-flex translate-x-1/2 rounded-full bg-primary px-3 py-1 text-xs font-medium text-white">
                  הפופולרי
                </span>
              )}
              <h3 className="text-lg font-semibold">{tier.name}</h3>
              <div className="mt-4 flex items-baseline gap-2">
                <span className="text-4xl font-bold">{tier.price}</span>
                <span className="text-slate-500">{tier.period}</span>
              </div>
              <p className="mt-2 text-sm text-slate-600">{tier.description}</p>
              <ul className="mt-6 space-y-3">
                {tier.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-sm">
                    <Check className="mt-0.5 h-4 w-4 text-primary-600" />
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
              <Link
                href={tier.href}
                className={`mt-6 inline-block w-full rounded-lg py-3 text-center text-sm font-medium ${
                  tier.popular
                    ? 'bg-primary text-white hover:bg-primary-700'
                    : 'border border-slate-300 text-slate-900 hover:bg-slate-50'
                }`}
              >
                {tier.cta}
              </Link>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
