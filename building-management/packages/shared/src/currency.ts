import { VAT_RATE_PCT } from './constants';

/** Format ILS money for display, defaulting to Hebrew locale. */
export function formatILS(amount: number | string, locale = 'he-IL'): string {
  const n = typeof amount === 'string' ? Number(amount) : amount;
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency: 'ILS',
    maximumFractionDigits: 2,
  }).format(n);
}

/** Round halves up to 2 decimal places. */
export function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

/**
 * Compute VAT breakdown for a gross or net amount.
 *
 * @param amount The amount in ILS
 * @param mode "inclusive" => amount already includes VAT; "exclusive" => amount is net
 * @param vatRatePct VAT percentage (default 17)
 */
export function computeVat(
  amount: number,
  mode: 'inclusive' | 'exclusive' = 'exclusive',
  vatRatePct = VAT_RATE_PCT,
): { subtotal: number; vat: number; total: number } {
  const rate = vatRatePct / 100;
  if (mode === 'inclusive') {
    const subtotal = round2(amount / (1 + rate));
    const vat = round2(amount - subtotal);
    return { subtotal, vat, total: round2(amount) };
  }
  const subtotal = round2(amount);
  const vat = round2(subtotal * rate);
  const total = round2(subtotal + vat);
  return { subtotal, vat, total };
}

/** Split an amount into n installments, distributing remainder to first months. */
export function splitInstallments(amount: number, n: number): number[] {
  if (n < 1) throw new Error('n must be >= 1');
  const base = Math.floor((amount * 100) / n) / 100;
  const remainder = round2(amount - base * n);
  const result: number[] = new Array(n).fill(base);
  // Distribute remainder cents to the first month(s).
  const remainderCents = Math.round(remainder * 100);
  for (let i = 0; i < remainderCents; i++) {
    result[i] = round2((result[i] ?? base) + 0.01);
  }
  return result;
}
