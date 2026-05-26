import { Building2, AlertCircle, Wallet, CheckCircle } from 'lucide-react';

export default function DashboardPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold">לוח בקרה</h1>
      <p className="mt-1 text-sm text-slate-600">סקירה כללית של הפעילות בחברת הניהול</p>

      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard icon={Building2} label="בניינים פעילים" value="12" sub="+1 החודש" tone="primary" />
        <KpiCard icon={AlertCircle} label="פניות פתוחות" value="8" sub="3 דחופות" tone="amber" />
        <KpiCard icon={Wallet} label="אחוז גבייה" value="94%" sub="↑ 2.3%" tone="green" />
        <KpiCard icon={CheckCircle} label="משימות היום" value="14" sub="5 הושלמו" tone="indigo" />
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-3">
        <section className="lg:col-span-2 rounded-2xl border border-slate-200 bg-white p-6">
          <h2 className="text-lg font-semibold">פעילות אחרונה</h2>
          <ul className="mt-4 space-y-3 text-sm">
            <li className="flex justify-between border-b border-slate-100 pb-3">
              <span>חיוב חודשי הופק - בניין הרצל 10</span>
              <span className="text-slate-400">לפני 5 דק׳</span>
            </li>
            <li className="flex justify-between border-b border-slate-100 pb-3">
              <span>פנייה חדשה: נזילה בדירה 12 (הרצל 10)</span>
              <span className="text-slate-400">לפני 23 דק׳</span>
            </li>
            <li className="flex justify-between border-b border-slate-100 pb-3">
              <span>צ׳ק חוזר - דירה 4ב (מגדל בן יהודה)</span>
              <span className="text-slate-400">לפני שעה</span>
            </li>
            <li className="flex justify-between">
              <span>חוזה שכירות חדש - דירה 7ג</span>
              <span className="text-slate-400">לפני שעתיים</span>
            </li>
          </ul>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-6">
          <h2 className="text-lg font-semibold">התראות חשובות</h2>
          <ul className="mt-4 space-y-3 text-sm">
            <li className="rounded-lg bg-amber-50 p-3 text-amber-900">
              ביטוח בניין פג בעוד 15 ימים
            </li>
            <li className="rounded-lg bg-red-50 p-3 text-red-900">
              צ׳ק חוזר ממתין לטיפול
            </li>
            <li className="rounded-lg bg-primary-50 p-3 text-primary-900">
              3 קריאות אורח חדשות
            </li>
          </ul>
        </section>
      </div>
    </div>
  );
}

function KpiCard({
  icon: Icon, label, value, sub, tone,
}: {
  icon: any; label: string; value: string; sub: string; tone: 'primary' | 'amber' | 'green' | 'indigo';
}) {
  const tones: Record<string, string> = {
    primary: 'bg-primary-50 text-primary-700',
    amber: 'bg-amber-50 text-amber-700',
    green: 'bg-emerald-50 text-emerald-700',
    indigo: 'bg-indigo-50 text-indigo-700',
  };
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5">
      <div className="flex items-center gap-3">
        <div className={`inline-flex h-10 w-10 items-center justify-center rounded-lg ${tones[tone]}`}>
          <Icon className="h-5 w-5" />
        </div>
        <div className="text-sm text-slate-500">{label}</div>
      </div>
      <div className="mt-3 text-3xl font-bold">{value}</div>
      <div className="mt-1 text-xs text-slate-500">{sub}</div>
    </div>
  );
}
