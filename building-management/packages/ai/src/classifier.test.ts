import { describe, it, expect } from 'vitest';
import { classifyTicket } from './classifier';

describe('classifyTicket (heuristic fallback)', () => {
  it('classifies leak in Hebrew as plumbing/high', async () => {
    const r = await classifyTicket('ישנה נזילה מתחת לכיור במטבח');
    expect(r.category).toBe('plumbing');
    expect(r.priority).toBe('high');
    expect(r.source).toBe('heuristic');
  });

  it('classifies elevator as elevator/high', async () => {
    const r = await classifyTicket('המעלית תקועה');
    expect(r.category).toBe('elevator');
    expect(r.priority).toBe('high');
  });

  it('classifies billing as billing/med', async () => {
    const r = await classifyTicket('יש לי בעיה עם החיוב החודשי');
    expect(r.category).toBe('billing');
  });

  it('defaults unknown text to other/med', async () => {
    const r = await classifyTicket('משהו לא ברור');
    expect(r.category).toBe('other');
    expect(r.priority).toBe('med');
  });
});
