import Link from 'next/link';
import { Upload, FolderArchive, AlertCircle } from 'lucide-react';

const docs = [
  { id: '1', title: 'ביטוח מבנה 2026', category: 'insurance', expires_at: '2026-06-15', expiring: true },
  { id: '2', title: 'חוזה ניקיון - אביב נקי', category: 'contract', expires_at: '2027-01-01' },
  { id: '3', title: 'אישור מעלית - יוני 2025', category: 'certificate', expires_at: '2026-06-30', expiring: true },
  { id: '4', title: 'תקנון בית', category: 'bylaws', expires_at: null },
];

const CAT_LABEL: Record<string, string> = {
  insurance: 'ביטוח',
  contract: 'חוזה',
  permit: 'אישור',
  blueprint: 'תוכניות',
  certificate: 'תעודה',
  bylaws: 'תקנון',
  minutes: 'פרוטוקול',
  other: 'אחר',
};

export default function DocumentsPage() {
  return (
    <div>
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">מסמכים</h1>
          <p className="mt-1 text-sm text-slate-600">כספת מסמכים פר-בניין, גרסאות, תזכורות תפוגה</p>
        </div>
        <button className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-700">
          <Upload className="h-4 w-4" />
          העלה מסמך
        </button>
      </header>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {docs.map((d) => (
          <div key={d.id} className="rounded-2xl border border-slate-200 bg-white p-5 hover:border-primary-200 hover:shadow-md transition">
            <div className="flex items-start justify-between">
              <div className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-primary-50 text-primary-700">
                <FolderArchive className="h-5 w-5" />
              </div>
              {d.expiring && (
                <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-1 text-xs text-amber-800">
                  <AlertCircle className="h-3 w-3" />
                  עתיד לפוג
                </span>
              )}
            </div>
            <h3 className="mt-4 font-semibold">{d.title}</h3>
            <p className="mt-1 text-xs text-slate-500">{CAT_LABEL[d.category]}</p>
            {d.expires_at && (
              <p className="mt-2 text-sm text-slate-600">פג בתאריך: {d.expires_at}</p>
            )}
            <Link href={`/documents/${d.id}`} className="mt-3 inline-block text-sm text-primary hover:underline">
              פרטים →
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}
