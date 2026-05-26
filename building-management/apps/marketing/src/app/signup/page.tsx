import Link from 'next/link';

export default function SignupPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-primary-50 to-white px-6">
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-xl">
        <h1 className="text-3xl font-bold">הרשמה לניסיון חינם</h1>
        <p className="mt-2 text-sm text-slate-600">30 יום ניסיון, ללא כרטיס אשראי</p>
        <form className="mt-6 space-y-4">
          <input
            type="text"
            placeholder="שם חברת הניהול"
            className="w-full rounded-lg border border-slate-300 px-4 py-3 text-right outline-none focus:border-primary"
          />
          <input
            type="email"
            placeholder="כתובת אימייל"
            className="w-full rounded-lg border border-slate-300 px-4 py-3 text-right outline-none focus:border-primary"
          />
          <input
            type="tel"
            placeholder="מספר טלפון (05X-XXX-XXXX)"
            className="w-full rounded-lg border border-slate-300 px-4 py-3 text-right outline-none focus:border-primary"
          />
          <input
            type="password"
            placeholder="סיסמה"
            className="w-full rounded-lg border border-slate-300 px-4 py-3 text-right outline-none focus:border-primary"
          />
          <button
            type="submit"
            className="w-full rounded-lg bg-primary py-3 font-medium text-white hover:bg-primary-700"
          >
            צרו חשבון
          </button>
        </form>
        <p className="mt-4 text-center text-sm text-slate-500">
          כבר רשומים?{' '}
          <Link href="https://app.building-management.co.il/login" className="text-primary hover:underline">
            התחברו
          </Link>
        </p>
      </div>
    </div>
  );
}
