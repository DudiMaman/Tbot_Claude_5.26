import Link from 'next/link';
import { Plus, AlertTriangle } from 'lucide-react';

const sampleChecks = [
  { id: '1', number: '0142', payer: 'דייר 8', amount: 350, due_date: '2026-06-15', status: 'scheduled' },
  { id: '2', number: '0143', payer: 'דייר 12', amount: 350, due_date: '2026-06-01', status: 'cleared' },
  { id: '3', number: '0144', payer: 'דייר 4', amount: 350, due_date: '2026-05-20', status: 'bounced' },
];

const STATUS_LABEL: Record<string, string> = {
  received: 'התקבל',
  scheduled: 'דחוי',
  deposited: 'הופקד',
  cleared: 'נפרע',
  bounced: 'חזר',
  replaced: 'הוחלף',
  voided: 'בוטל',
};

export default function ChecksPage() {
  return (
    <div>
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">צ׳קים</h1>
          <p className="mt-1 text-sm text-slate-600">ניהול צ׳קים, הפקדות וצ׳קים חוזרים</p>
        </div>
        <div className="flex gap-2">
          <Link href="/checks/bounced" className="inline-flex items-center gap-2 rounded-lg border border-amber-300 bg-amber-50 px-4 py-2 text-sm text-amber-900 hover:bg-amber-100">
            <AlertTriangle className="h-4 w-4" />
            צ׳קים חוזרים (1)
          </Link>
          <Link href="/checks/new" className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-700">
            <Plus className="h-4 w-4" />
            צ׳ק חדש
          </Link>
        </div>
      </header>

      <div className="mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-white">
        <table className="w-full text-right text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-6 py-3">מס׳ צ׳ק</th>
              <th className="px-6 py-3">משלם</th>
              <th className="px-6 py-3">סכום</th>
              <th className="px-6 py-3">תאריך פירעון</th>
              <th className="px-6 py-3">סטטוס</th>
              <th className="px-6 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {sampleChecks.map((c) => (
              <tr key={c.id} className="border-t border-slate-100 hover:bg-slate-50">
                <td className="px-6 py-4 font-mono text-sm">{c.number}</td>
                <td className="px-6 py-4">{c.payer}</td>
                <td className="px-6 py-4">₪{c.amount}</td>
                <td className="px-6 py-4">{c.due_date}</td>
                <td className="px-6 py-4">
                  <span className={`rounded-full px-2 py-1 text-xs ${
                    c.status === 'cleared' ? 'bg-emerald-100 text-emerald-800' :
                    c.status === 'bounced' ? 'bg-red-100 text-red-800' :
                    'bg-slate-100 text-slate-800'
                  }`}>
                    {STATUS_LABEL[c.status]}
                  </span>
                </td>
                <td className="px-6 py-4 text-left">
                  <Link href={`/checks/${c.id}`} className="text-primary hover:underline">
                    פרטים
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
