import Link from 'next/link';
import {
  LayoutDashboard, Building2, Home, Users, FileText, ListChecks,
  MessageSquare, Wallet, Wrench, Bell, Settings, ScrollText,
  Receipt, Megaphone, Vote, FolderArchive, Bot, ShoppingBag, BarChart3,
} from 'lucide-react';

const items = [
  { href: '/', label: 'לוח בקרה', icon: LayoutDashboard },
  { href: '/buildings', label: 'בניינים', icon: Building2 },
  { href: '/apartments', label: 'דירות', icon: Home },
  { href: '/people', label: 'אנשים', icon: Users },
  { href: '/rental-contracts', label: 'חוזי שכירות', icon: FileText },
  { href: '/tasks', label: 'משימות', icon: ListChecks },
  { href: '/tickets', label: 'פניות', icon: Wrench },
  { href: '/charges', label: 'חיובים', icon: Wallet },
  { href: '/invoices', label: 'חשבוניות וקבלות', icon: Receipt },
  { href: '/checks', label: 'צ׳קים', icon: ScrollText },
  { href: '/documents', label: 'מסמכים', icon: FolderArchive },
  { href: '/vendors', label: 'ספקים', icon: ShoppingBag },
  { href: '/bulletin', label: 'לוח מודעות', icon: Megaphone },
  { href: '/polls', label: 'סקרים', icon: Vote },
  { href: '/whatsapp', label: 'תקשורת', icon: MessageSquare },
  { href: '/ai-bot', label: 'בוט AI', icon: Bot },
  { href: '/reports', label: 'דוחות', icon: BarChart3 },
  { href: '/notifications', label: 'התראות', icon: Bell },
  { href: '/settings', label: 'הגדרות', icon: Settings },
];

export function Sidebar() {
  return (
    <aside className="w-64 shrink-0 border-l border-slate-200 bg-white">
      <div className="border-b border-slate-200 p-4">
        <Link href="/" className="text-lg font-bold text-primary">
          ניהול מבנים
        </Link>
      </div>
      <nav className="p-3">
        {items.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className="mb-1 flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-slate-700 transition hover:bg-slate-100"
          >
            <Icon className="h-4 w-4 text-slate-400" />
            <span>{label}</span>
          </Link>
        ))}
      </nav>
    </aside>
  );
}
