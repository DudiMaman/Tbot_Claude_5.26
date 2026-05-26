const testimonials = [
  {
    quote: 'עברנו מאקסל ופנקס לפלטפורמה. החזר השקעה תוך 3 חודשים. הדיירים מרוצים, אנחנו מרוויחים יותר.',
    name: 'דנה כהן',
    role: 'מנכ"לית, חברת ניהול בית-אב',
  },
  {
    quote: 'הבוט בWhatsApp עונה ל-80% מהשאלות. אנחנו מטפלים רק במה שחשוב באמת.',
    name: 'יוסי לוי',
    role: 'מנהל תפעול, ניהול הירוק',
  },
  {
    quote: 'טיפול בצ׳קים חוזרים שהיה לוקח שעות, הופך ל-2 קליקים. שינוי משחק.',
    name: 'רונית אביב',
    role: 'מנהלת כספים, ועד פעיל',
  },
];

export function Testimonials() {
  return (
    <section className="bg-slate-50 px-6 py-20">
      <div className="mx-auto max-w-6xl">
        <h2 className="text-center text-4xl font-bold">מה אומרים הלקוחות</h2>
        <div className="mt-12 grid gap-6 md:grid-cols-3">
          {testimonials.map((t) => (
            <blockquote key={t.name} className="rounded-2xl border border-slate-200 bg-white p-8">
              <p className="text-lg italic text-slate-800">"{t.quote}"</p>
              <footer className="mt-6">
                <p className="font-semibold">{t.name}</p>
                <p className="text-sm text-slate-500">{t.role}</p>
              </footer>
            </blockquote>
          ))}
        </div>
      </div>
    </section>
  );
}
