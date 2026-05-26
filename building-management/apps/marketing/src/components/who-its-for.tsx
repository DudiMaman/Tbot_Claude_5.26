const personas = [
  {
    label: 'חברות ניהול',
    title: 'ניהול תפעולי, פיננסי ותקשורתי במקום אחד',
    bullets: [
      'תצוגת מפה של כל הבניינים עם מצב גבייה ופניות',
      'גבייה אוטומטית, ניהול ספקים ותשלומי מס"ב',
      'דוחות ניהוליים וכספיים, ייצוא לחשבשבת/ריווחית',
      'אפליקציית דסקטופ למקצוענים',
    ],
  },
  {
    label: 'ועדי בית',
    title: 'אפס בירוקרטיה, מקסימום שקיפות',
    bullets: [
      'סקרים והצבעות עם חתימה דיגיטלית',
      'לוח מודעות בעברית עם התראות פוש',
      'יומן הוצאות ויתרת קופה',
      'גישה לכל המסמכים המשפטיים של הבניין',
    ],
  },
  {
    label: 'בעלי דירות',
    title: 'מעקב כספי גם כשאתם לא גרים בבניין',
    bullets: [
      'תצוגת היסטוריית תשלומים מלאה לדירה',
      'התראה כשהשוכר מאחר בתשלום',
      'אפשרות לכסות תשלום שהשוכר פספס',
      'הזמנת שוכר חדש דרך האפליקציה',
    ],
  },
  {
    label: 'שוכרים',
    title: 'תשלום קל ופניות מהירות',
    bullets: [
      'תשלום כרטיס אשראי או הוראת קבע',
      'דיווח תקלות עם תמונה',
      'פתיחת שער חניה מהטלפון',
      'בוט WhatsApp עונה תמיד',
    ],
  },
];

export function WhoItsFor() {
  return (
    <section id="who" className="bg-slate-50 px-6 py-20">
      <div className="mx-auto max-w-6xl">
        <h2 className="text-center text-4xl font-bold">למי זה מתאים</h2>
        <p className="mx-auto mt-3 max-w-2xl text-center text-slate-600">
          בנינו את המערכת מהבסיס לעולם הישראלי — חברות ניהול, ועדי בית, בעלי דירות, ושוכרים.
        </p>
        <div className="mt-12 grid gap-6 md:grid-cols-2">
          {personas.map((p) => (
            <div key={p.label} className="rounded-2xl border border-slate-200 bg-white p-8">
              <div className="inline-flex rounded-full bg-primary-100 px-3 py-1 text-xs font-medium text-primary-700">
                {p.label}
              </div>
              <h3 className="mt-4 text-xl font-semibold">{p.title}</h3>
              <ul className="mt-4 space-y-2 text-slate-600">
                {p.bullets.map((b) => (
                  <li key={b} className="flex items-start gap-2">
                    <span className="mt-2 inline-block h-1.5 w-1.5 rounded-full bg-primary-500" />
                    <span>{b}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
