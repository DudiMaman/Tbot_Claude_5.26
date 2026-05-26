/**
 * MASAV file builder — Israeli inter-bank clearing format.
 * See: https://www.masav.co.il
 *
 * MASAV files are fixed-width text. Each record is exactly 88 bytes
 * (some banks accept 128/192) and right-padded with spaces.
 *
 * This implementation produces the most common 88-byte "B" format used for
 * outgoing transfers (vendor payouts). Real production code must validate
 * against the bank's spec; we expose a builder that's covered by unit tests
 * and pluggable so each bank can override.
 *
 * Reference (high level only — confirm with your bank):
 *   - Header record: institution code, file date, account info
 *   - Detail records: one per payment (vendor name, amount in agorot, IBAN)
 *   - Trailer record: total amount + record count + checksum
 */

export interface MasavParty {
  bank_code: string;        // 3 digits, e.g. "012" (Hapoalim)
  branch_code: string;      // 3 digits
  account_number: string;   // up to 9 digits, right-justified
  name: string;             // up to 16 Hebrew chars (Windows-1255 in real spec)
  vat_id?: string;          // 9 digits (חברה / עוסק)
}

export interface MasavPayment {
  payee: MasavParty;
  amount_ils: number;       // ILS; we convert to agorot internally
  reference?: string;
}

export interface MasavFile {
  payer: MasavParty;
  file_date: Date;
  institution_code: string; // assigned by MASAV to each institution (e.g., a mgmt company)
  payments: MasavPayment[];
}

const pad = (s: string, n: number, char = ' ', side: 'left' | 'right' = 'right'): string => {
  if (s.length >= n) return s.slice(0, n);
  const fill = char.repeat(n - s.length);
  return side === 'right' ? s + fill : fill + s;
};

const padLeft = (s: string | number, n: number, char = '0') => pad(String(s), n, char, 'left');
const padRight = (s: string, n: number) => pad(s, n, ' ', 'right');

function formatDateYYYYMMDD(d: Date): string {
  const y = d.getFullYear();
  const m = padLeft(d.getMonth() + 1, 2);
  const day = padLeft(d.getDate(), 2);
  return `${y}${m}${day}`;
}

/** Builds the MASAV text content. */
export function buildMasavFile(file: MasavFile): string {
  const dateStr = formatDateYYYYMMDD(file.file_date);

  // Header (88 bytes)
  // Layout (simplified; align to your bank's spec):
  //  pos  1- 1  type "H"
  //  pos  2- 9  institution_code (8)
  //  pos 10-17 file_date YYYYMMDD
  //  pos 18-21 bank_code (4)
  //  pos 22-24 branch_code (3)
  //  pos 25-33 account_number (9)
  //  pos 34-49 payer_name (16)
  //  pos 50-88 reserved (spaces)
  const header =
    'H' +
    padRight(file.institution_code, 8) +
    dateStr +
    padRight(file.payer.bank_code, 4) +
    padRight(file.payer.branch_code, 3) +
    padLeft(file.payer.account_number, 9) +
    padRight(file.payer.name, 16) +
    pad('', 39, ' ', 'right');

  const lines: string[] = [header.slice(0, 88)];
  let totalAgorot = 0;

  // Detail records
  // Layout (simplified):
  //  pos  1- 1 type "D"
  //  pos  2- 4 bank_code (3)
  //  pos  5- 7 branch_code (3)
  //  pos  8-16 account_number (9)
  //  pos 17-32 payee_name (16)
  //  pos 33-41 amount in agorot (9, leading zeros)
  //  pos 42-50 reference (9)
  //  pos 51-88 reserved
  for (const p of file.payments) {
    const agorot = Math.round(p.amount_ils * 100);
    totalAgorot += agorot;
    const line =
      'D' +
      padRight(p.payee.bank_code, 3) +
      padRight(p.payee.branch_code, 3) +
      padLeft(p.payee.account_number, 9) +
      padRight(p.payee.name, 16) +
      padLeft(agorot, 9) +
      padRight(p.reference ?? '', 9) +
      pad('', 38, ' ', 'right');
    lines.push(line.slice(0, 88));
  }

  // Trailer (88 bytes)
  //  pos  1- 1 type "T"
  //  pos  2- 9 total agorot (8)
  //  pos 10-14 record count (5)
  //  pos 15-88 reserved
  const trailer =
    'T' +
    padLeft(totalAgorot, 8) +
    padLeft(file.payments.length, 5) +
    pad('', 74, ' ', 'right');
  lines.push(trailer.slice(0, 88));

  return lines.join('\n');
}

/** Returns a checksum for verification (simple modulo over agorot total + count). */
export function masavChecksum(file: MasavFile): string {
  const total = file.payments.reduce((acc, p) => acc + Math.round(p.amount_ils * 100), 0);
  return String((total + file.payments.length * 7) % 99991);
}
