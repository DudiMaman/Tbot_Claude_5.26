import { describe, it, expect } from 'vitest';
import { buildMasavFile, masavChecksum } from './index';

describe('buildMasavFile', () => {
  const file = {
    payer: {
      bank_code: '012',
      branch_code: '460',
      account_number: '123456',
      name: 'חברה בעמ',
      vat_id: '514000001',
    },
    file_date: new Date('2026-06-01'),
    institution_code: '12345678',
    payments: [
      {
        payee: {
          bank_code: '011',
          branch_code: '200',
          account_number: '987654321',
          name: 'נחמני שרברב',
        },
        amount_ils: 1500.5,
      },
      {
        payee: {
          bank_code: '010',
          branch_code: '100',
          account_number: '555444',
          name: 'ארז חשמלאי',
        },
        amount_ils: 800,
      },
    ],
  };

  it('produces header + N detail + trailer records', () => {
    const text = buildMasavFile(file);
    const lines = text.split('\n');
    expect(lines).toHaveLength(1 + 2 + 1);
  });

  it('each line is exactly 88 chars', () => {
    const lines = buildMasavFile(file).split('\n');
    for (const line of lines) {
      expect(line).toHaveLength(88);
    }
  });

  it('trailer contains correct total in agorot', () => {
    const text = buildMasavFile(file);
    const trailer = text.split('\n')[3];
    // 1500.50 + 800.00 = 2300.50 -> 230050 agorot
    expect(trailer).toMatch(/^T\s*0?00230050/);
  });

  it('checksum is deterministic', () => {
    expect(masavChecksum(file)).toBe(masavChecksum(file));
  });
});
