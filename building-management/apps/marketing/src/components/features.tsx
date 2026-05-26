import {
  Wallet, Wrench, MessageCircle, Bot, FileText, Receipt, ListChecks,
  KeyRound, FolderArchive, Megaphone, CheckSquare, BarChart3,
} from 'lucide-react';

const features = [
  { icon: Wallet, title: 'גבייה חודשית אוטומטית', subtitle: 'תשלום בכרטיס אשראי, עד 12 תשלומים, הוראת קבע' },
  { icon: Wrench, title: 'ניהול פניות שירות', subtitle: 'דיווח עם תמונה, סיווג אוטומטי ב-AI, מעקב בזמן אמת' },
  { icon: MessageCircle, title: 'שירות לקוחות בוואטסאפ', subtitle: 'אינטגרציה ישירה עם WhatsApp Business' },
  { icon: Bot, title: 'בוט AI 24/7', subtitle: 'מענה אוטומטי בעברית, פותח קריאות, בודק יתרות' },
  { icon: FileText, title: 'חשבוניות תואמות רשות המסים', subtitle: 'הקצאה דיגיטלית, מספור רציף, חשבונית זיכוי' },
  { icon: Receipt, title: 'ניהול צ׳קים', subtitle: 'הפקדות, צ׳קים דחויים, טיפול אוטומטי בצ׳קים חוזרים' },
  { icon: ListChecks, title: 'ניהול משימות אחזקה', subtitle: 'לוז יומי לאיש האחזקה, צילום לפני/אחרי' },
  { icon: KeyRound, title: 'פתיחת שערים מהאפליקציה', subtitle: 'שער חניה, קודי אורח, יומן גישה' },
  { icon: FolderArchive, title: 'כספת מסמכים לבניין', subtitle: 'ביטוחים, חוזים, אישורים — עם תזכורת תפוגה' },
  { icon: Megaphone, title: 'לוח מודעות חכם', subtitle: 'הודעות לבעלים בלבד / לכולם, התראות אוטומטיות' },
  { icon: CheckSquare, title: 'סקרים והצבעות', subtitle: 'הצבעת ועד עם חתימה דיגיטלית' },
  { icon: BarChart3, title: 'דוחות ואנליטיקה', subtitle: 'אחוז גבייה, AR aging, ביצועי אחזקה' },
];

export function Features() {
  return (
    <section id="features" className="px-6 py-20">
      <div className="mx-auto max-w-6xl">
        <h2 className="text-center text-4xl font-bold">כל מה שחברת ניהול צריכה</h2>
        <p className="mx-auto mt-3 max-w-2xl text-center text-slate-600">
          פלטפורמה אחת, כל הכלים. בלי לעבור בין מערכות, בלי לנהל אקסלים.
        </p>
        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {features.map(({ icon: Icon, title, subtitle }) => (
            <div
              key={title}
              className="group rounded-2xl border border-slate-200 bg-white p-6 transition hover:border-primary-200 hover:shadow-lg"
            >
              <div className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-primary-50 text-primary-700 transition group-hover:bg-primary-100">
                <Icon className="h-6 w-6" />
              </div>
              <h3 className="mt-4 text-lg font-semibold">{title}</h3>
              <p className="mt-2 text-sm text-slate-600">{subtitle}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
