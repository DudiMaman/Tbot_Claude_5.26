import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

export function Hero() {
  return (
    <section className="relative overflow-hidden px-6 py-20 md:py-32">
      <div className="mx-auto max-w-6xl text-center">
        <div className="inline-flex items-center gap-2 rounded-full bg-primary-50 px-4 py-2 text-sm text-primary-700">
          <span>חדש</span>
          <span className="text-primary-300">•</span>
          <span>בוט AI ב-WhatsApp לשירות לקוחות 24/7</span>
        </div>
        <h1 className="mt-6 text-5xl font-bold leading-tight md:text-7xl">
          ניהול מבנים
          <br />
          <span className="bg-gradient-to-l from-primary-600 to-indigo-500 bg-clip-text text-transparent">
            בלי כאב ראש
          </span>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-slate-600 md:text-xl">
          פלטפורמה אחת לחברת הניהול, לדיירים, לבעלי דירות ולאנשי האחזקה.
          גבייה אוטומטית, פניות שירות, וואטסאפ, בוט AI, פתיחת שערי חניה,
          חשבוניות תואמות רשות המסים ועוד.
        </p>
        <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Link
            href="/signup"
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-8 py-4 text-base font-medium text-white shadow-lg shadow-primary-300/30 transition hover:bg-primary-700"
          >
            התחילו ניסיון חינם
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <Link
            href="/demo"
            className="rounded-lg border border-slate-300 bg-white px-8 py-4 text-base font-medium hover:bg-slate-50"
          >
            קבעו הדגמה
          </Link>
        </div>
        <p className="mt-6 text-sm text-slate-500">
          30 יום ניסיון חינם • ללא כרטיס אשראי • הקמה תוך 10 דקות
        </p>
      </div>

      {/* Background gradient blob */}
      <div className="pointer-events-none absolute inset-x-0 top-1/2 -z-10 -translate-y-1/2 transform">
        <div className="mx-auto h-96 w-3/4 rounded-full bg-gradient-to-r from-primary-100 via-indigo-100 to-pink-100 blur-3xl opacity-50" />
      </div>
    </section>
  );
}
