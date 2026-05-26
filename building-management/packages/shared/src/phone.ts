import { parsePhoneNumberFromString, type CountryCode } from 'libphonenumber-js';

const DEFAULT_COUNTRY: CountryCode = 'IL';

/** Parse a phone string and return E.164 (e.g. "+972501234567") or null. */
export function toE164(input: string, country: CountryCode = DEFAULT_COUNTRY): string | null {
  const phone = parsePhoneNumberFromString(input, country);
  if (!phone || !phone.isValid()) return null;
  return phone.number;
}

/** Format a phone for human display in Israel. */
export function formatPhoneHe(input: string): string {
  const phone = parsePhoneNumberFromString(input, DEFAULT_COUNTRY);
  if (!phone) return input;
  return phone.formatNational();
}

export function isIsraeliMobile(e164: string): boolean {
  return /^\+9725\d{8}$/.test(e164);
}
