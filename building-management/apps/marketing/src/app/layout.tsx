import './globals.css';
import { Heebo } from 'next/font/google';
import type { Metadata } from 'next';

const heebo = Heebo({ subsets: ['hebrew', 'latin'], display: 'swap' });

export const metadata: Metadata = {
  title: 'ניהול מבנים - פלטפורמת CRM מודרנית לחברות ניהול',
  description: 'פלטפורמה אחת לחברת הניהול, לדיירים, לבעלי דירות ולאנשי האחזקה. גבייה אוטומטית, פניות שירות, וואטסאפ, בוט AI ועוד.',
  openGraph: {
    title: 'ניהול מבנים',
    description: 'פלטפורמה אחת לכל ניהול הבניין',
    locale: 'he_IL',
    type: 'website',
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="he" dir="rtl">
      <body className={heebo.className}>{children}</body>
    </html>
  );
}
