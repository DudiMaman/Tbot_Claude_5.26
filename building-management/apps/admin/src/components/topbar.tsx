import { Search, Bell, User } from 'lucide-react';

export function Topbar() {
  return (
    <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
      <div className="relative w-96">
        <Search className="absolute right-3 top-3 h-4 w-4 text-slate-400" />
        <input
          type="text"
          placeholder="חיפוש..."
          className="w-full rounded-lg border border-slate-200 bg-slate-50 py-2 pr-10 ps-4 text-sm outline-none focus:border-primary"
        />
      </div>
      <div className="flex items-center gap-3">
        <button className="rounded-lg p-2 hover:bg-slate-100">
          <Bell className="h-5 w-5 text-slate-600" />
        </button>
        <button className="flex items-center gap-2 rounded-lg p-2 hover:bg-slate-100">
          <User className="h-5 w-5 text-slate-600" />
        </button>
      </div>
    </header>
  );
}
