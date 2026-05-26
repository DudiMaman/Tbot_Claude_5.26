'use client';
import { useState } from 'react';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  return (
    <div className="flex min-h-screen items-center justify-center px-6">
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-xl">
        <h1 className="text-2xl font-bold">התחברות</h1>
        <p className="mt-2 text-sm text-slate-600">לחברות ניהול מבנים</p>
        <form
          className="mt-6 space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            // Auth happens via Supabase; this is a placeholder
            alert('Login flow to be wired up to Supabase Auth');
          }}
        >
          <input
            type="email"
            placeholder="אימייל"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-4 py-3 outline-none focus:border-primary"
          />
          <input
            type="password"
            placeholder="סיסמה"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-4 py-3 outline-none focus:border-primary"
          />
          <button
            type="submit"
            className="w-full rounded-lg bg-primary py-3 font-medium text-white hover:bg-primary-700"
          >
            התחברות
          </button>
        </form>
        <p className="mt-4 text-center text-sm text-slate-500">
          אין לכם חשבון?{' '}
          <a href="/signup" className="text-primary hover:underline">הירשמו</a>
        </p>
      </div>
    </div>
  );
}
