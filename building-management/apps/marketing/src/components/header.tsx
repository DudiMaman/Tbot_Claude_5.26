import Link from 'next/link';

export function Header() {
  return (
    <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" className="text-xl font-bold text-primary">
          ניהול מבנים
        </Link>
        <nav className="hidden gap-6 text-sm text-slate-700 md:flex">
          <a href="#features" className="hover:text-primary">פיצ'רים</a>
          <a href="#who" className="hover:text-primary">למי זה מתאים</a>
          <a href="#pricing" className="hover:text-primary">מחירים</a>
          <a href="#faq" className="hover:text-primary">שאלות נפוצות</a>
        </nav>
        <div className="flex gap-3">
          <Link
            href="https://app.building-management.co.il/login"
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm hover:bg-slate-50"
          >
            התחברות
          </Link>
          <Link
            href="/signup"
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
          >
            התחילו ניסיון חינם
          </Link>
        </div>
      </div>
    </header>
  );
}
