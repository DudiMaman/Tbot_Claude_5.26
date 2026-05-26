import Link from 'next/link';
import { Plus, FileText } from 'lucide-react';

const TYPE_LABEL: Record<string, string> = {
  tax_invoice: 'חשבונית מס',
  receipt: 'קבלה',
  tax_invoice_receipt: 'חשבונית מס/קבלה',
  credit_note: 'חשבונית זיכוי',
};

const sampleInvoices = [
  { id: '1', number: '00012', type: 'tax_invoice_receipt', customer: 'דייר 1', amount: 350, issued_at: '2026-05-25', status: 'issued', ita: 'MOCK-XYZ' },
  { id: '2', number: '00011', type: 'tax_invoice_receipt', customer: 'דייר 2', amount: 350, issued_at: '2026-05-25', status: 'sent', ita: null },
  { id: '3', number: '00001', type: 'credit_note', customer: 'דייר 7', amount: -350, issued_at: '2026-05-20', status: 'issued', ita: null },
];

export default function InvoicesPage() {
  return (
    <div>
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">חשבוניות וקבלות</h1>
          <p className="mt-1 text-sm text-slate-600">תואם רשות המסים. מספור רציף. אינטגרציה דיגיטלית.</p>
        </div>
        <div className="flex gap-2">
          <Link href="/invoices/series" className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm hover:bg-slate-50">
            ניהול סדרות
          </Link>
          <Link href="/invoices/new" className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-700">
            <Plus className="h-4 w-4" />
            הפק חשבונית
          </Link>
        </div>
      </header>

      <div className="mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-white">
        <table className="w-full text-right text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-6 py-3">מס׳</th>
              <th className="px-6 py-3">סוג</th>
              <th className="px-6 py-3">לקוח</th>
              <th className="px-6 py-3">סכום</th>
              <th className="px-6 py-3">תאריך</th>
              <th className="px-6 py-3">סטטוס</th>
              <th className="px-6 py-3">מס׳ הקצאה</th>
              <th className="px-6 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {sampleInvoices.map((inv) => (
              <tr key={inv.id} className="border-t border-slate-100 hover:bg-slate-50">
                <td className="px-6 py-4 font-mono text-sm">{inv.number}</td>
                <td className="px-6 py-4">{TYPE_LABEL[inv.type]}</td>
                <td className="px-6 py-4">{inv.customer}</td>
                <td className={`px-6 py-4 ${inv.amount < 0 ? 'text-red-600' : ''}`}>
                  ₪{Math.abs(inv.amount).toLocaleString('he-IL', { minimumFractionDigits: 2 })}
                </td>
                <td className="px-6 py-4">{inv.issued_at}</td>
                <td className="px-6 py-4">
                  <span className="rounded-full bg-emerald-100 px-2 py-1 text-xs text-emerald-800">{inv.status}</span>
                </td>
                <td className="px-6 py-4 font-mono text-xs text-slate-500">{inv.ita ?? '—'}</td>
                <td className="px-6 py-4 text-left">
                  <button className="inline-flex items-center gap-1 text-primary hover:underline">
                    <FileText className="h-4 w-4" />
                    PDF
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
