const faqs = [
  { q: 'כמה זמן לוקח להקים את המערכת?', a: 'ההקמה לוקחת בין 10 דקות ליום עבודה, תלוי בכמות הבניינים. אנחנו מספקים תהליך הטמעה מובנה עם תמיכה.' },
  { q: 'האם אני יכול לייבא נתונים קיימים?', a: 'כן. תומכים בייבוא דירות, דיירים, וחיובים מ-CSV או Excel. ייבוא ספקים וחוזים אפשרי דרך תמיכה.' },
  { q: 'איך עובדת הגבייה אוטומטית?', a: 'באמצעות חיבור ל-Tranzila (תקן PCI). הדייר מזין כרטיס פעם אחת, החיוב מתבצע אוטומטית כל חודש. תמיכה ב-1-12 תשלומים.' },
  { q: 'מה לגבי הגנת הפרטיות?', a: 'נתונים בענן ב-EU-West (אירופה), הצפנה ב-rest וב-transit, תאימות לחוק הגנת הפרטיות הישראלי + GDPR.' },
  { q: 'יש אפליקציה לדיירים?', a: 'כן — אפליקציית iOS ו-Android. דיירים יכולים להוריד אותה ולסרוק קוד QR מהפלייר שמופק אוטומטית כשהקמתם בניין.' },
  { q: 'איך עובד הבוט AI?', a: 'הבוט מבוסס Claude מבית Anthropic, עונה בעברית, יכול לבדוק יתרה, לפתוח קריאות שירות, ולהסלים לבן אדם כשצריך.' },
  { q: 'תומך בחוזי שכירות?', a: 'בהחלט. תומכים בכל התרחישים: בעלים גר, בעלים שמשכיר ושוכר משלם, בעלים שמשכיר ובעלים משלם, וגם פיצול 50/50.' },
  { q: 'מה לגבי חשבוניות?', a: 'הפקת חשבונית מס, קבלה, חשבונית מס/קבלה, וחשבונית זיכוי — כולן תואמות רשות המסים עם מספור רציף וחתימה דיגיטלית.' },
];

export function Faq() {
  return (
    <section id="faq" className="px-6 py-20">
      <div className="mx-auto max-w-4xl">
        <h2 className="text-center text-4xl font-bold">שאלות נפוצות</h2>
        <div className="mt-12 space-y-4">
          {faqs.map((f) => (
            <details
              key={f.q}
              className="group rounded-xl border border-slate-200 bg-white p-6 open:bg-slate-50"
            >
              <summary className="flex cursor-pointer items-center justify-between text-lg font-semibold">
                <span>{f.q}</span>
                <span className="ms-2 text-slate-400 group-open:rotate-180 transition">▾</span>
              </summary>
              <p className="mt-4 text-slate-600">{f.a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
