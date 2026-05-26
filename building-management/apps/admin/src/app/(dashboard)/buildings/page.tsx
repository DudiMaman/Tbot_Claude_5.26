import Link from 'next/link';
import { Plus } from 'lucide-react';

const buildings = [
  { id: '1', name: 'הרצל 10', city: 'תל אביב', apartments: 20, occupied: 18, collectionRate: 96, openTickets: 2 },
  { id: '2', name: 'מגדל בן יהודה', city: 'תל אביב', apartments: 10, occupied: 9, collectionRate: 88, openTickets: 1 },
];

export default function BuildingsPage() {
  return (
    <div>
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">בניינים</h1>
          <p className="mt-1 text-sm text-slate-600">{buildings.length} בניינים פעילים</p>
        </div>
        <Link
          href="/buildings/new"
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
        >
          <Plus className="h-4 w-4" />
          בניין חדש
        </Link>
      </header>

      <div className="mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-white">
        <table className="w-full text-right text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-6 py-3">שם</th>
              <th className="px-6 py-3">עיר</th>
              <th className="px-6 py-3">דירות</th>
              <th className="px-6 py-3">תפוסה</th>
              <th className="px-6 py-3">אחוז גבייה</th>
              <th className="px-6 py-3">פניות פתוחות</th>
              <th className="px-6 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {buildings.map((b) => (
              <tr key={b.id} className="border-t border-slate-100 hover:bg-slate-50">
                <td className="px-6 py-4 font-medium">{b.name}</td>
                <td className="px-6 py-4 text-slate-600">{b.city}</td>
                <td className="px-6 py-4">{b.apartments}</td>
                <td className="px-6 py-4">{b.occupied} / {b.apartments}</td>
                <td className="px-6 py-4">
                  <span className={`inline-flex rounded-full px-2 py-1 text-xs ${
                    b.collectionRate >= 90 ? 'bg-emerald-100 text-emerald-800' :
                    b.collectionRate >= 70 ? 'bg-amber-100 text-amber-800' :
                    'bg-red-100 text-red-800'
                  }`}>
                    {b.collectionRate}%
                  </span>
                </td>
                <td className="px-6 py-4">{b.openTickets}</td>
                <td className="px-6 py-4 text-left">
                  <Link href={`/buildings/${b.id}`} className="text-primary hover:underline">
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
