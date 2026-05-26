import './globals.css';
import { Heebo } from 'next/font/google';
import type { Metadata } from 'next';

const heebo = Heebo({ subsets: ['hebrew', 'latin'], display: 'swap' });

export const metadata: Metadata = {
  title: 'לוח ניהול - Building Management',
  description: 'מסך ניהול לחברות ניהול מבנים',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="he" dir="rtl">
      <body className={heebo.className}>{children}</body>
    </html>
  );
}
