import Link from 'next/link';

export function Footer() {
  return (
    <footer className="border-t border-slate-200 bg-white px-6 py-12">
      <div className="mx-auto grid max-w-6xl gap-8 md:grid-cols-4">
        <div>
          <h3 className="text-lg font-bold text-primary">ניהול מבנים</h3>
          <p className="mt-3 text-sm text-slate-600">
            פלטפורמת CRM מודרנית לחברות ניהול ואחזקת מבנים בישראל.
          </p>
        </div>
        <div>
          <h4 className="font-semibold">מוצר</h4>
          <ul className="mt-3 space-y-2 text-sm text-slate-600">
            <li><Link href="#features" className="hover:text-primary">פיצ'רים</Link></li>
            <li><Link href="#pricing" className="hover:text-primary">מחירים</Link></li>
            <li><Link href="/demo" className="hover:text-primary">הדגמה</Link></li>
          </ul>
        </div>
        <div>
          <h4 className="font-semibold">חברה</h4>
          <ul className="mt-3 space-y-2 text-sm text-slate-600">
            <li><Link href="/about" className="hover:text-primary">אודות</Link></li>
            <li><Link href="/blog" className="hover:text-primary">בלוג</Link></li>
            <li><Link href="/contact" className="hover:text-primary">צור קשר</Link></li>
          </ul>
        </div>
        <div>
          <h4 className="font-semibold">משפטי</h4>
          <ul className="mt-3 space-y-2 text-sm text-slate-600">
            <li><Link href="/legal/terms" className="hover:text-primary">תנאי שימוש</Link></li>
            <li><Link href="/legal/privacy" className="hover:text-primary">מדיניות פרטיות</Link></li>
            <li><Link href="/legal/dpa" className="hover:text-primary">DPA</Link></li>
          </ul>
        </div>
      </div>
      <div className="mx-auto mt-12 max-w-6xl border-t border-slate-200 pt-6 text-center text-sm text-slate-500">
        © {new Date().getFullYear()} ניהול מבנים. כל הזכויות שמורות.
      </div>
    </footer>
  );
}
