import { describe, it, expect } from 'vitest';
import { computeVat, splitInstallments, round2, formatILS } from './currency';

describe('computeVat', () => {
  it('exclusive: 100 -> 100 + 17 = 117', () => {
    expect(computeVat(100, 'exclusive')).toEqual({ subtotal: 100, vat: 17, total: 117 });
  });
  it('inclusive: 117 -> 100 + 17', () => {
    expect(computeVat(117, 'inclusive')).toEqual({ subtotal: 100, vat: 17, total: 117 });
  });
  it('zero', () => {
    expect(computeVat(0)).toEqual({ subtotal: 0, vat: 0, total: 0 });
  });
});

describe('splitInstallments', () => {
  it('splits 350 into 6 installments correctly', () => {
    const parts = splitInstallments(350, 6);
    expect(parts).toHaveLength(6);
    const sum = parts.reduce((a, b) => round2(a + b), 0);
    expect(sum).toBe(350);
  });
  it('handles non-divisible amounts (350.05 into 3)', () => {
    const parts = splitInstallments(350.05, 3);
    expect(parts).toHaveLength(3);
    const sum = parts.reduce((a, b) => round2(a + b), 0);
    expect(sum).toBe(350.05);
  });
});

describe('formatILS', () => {
  it('formats Hebrew ILS', () => {
    const result = formatILS(350);
    expect(result).toContain('350');
    expect(result).toMatch(/₪|ILS/);
  });
});
