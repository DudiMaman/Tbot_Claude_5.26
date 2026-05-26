/**
 * Tests for the bill-payer resolution algorithm — the heart of SPEC §3.6.
 *
 * These tests run against a fake DbService that returns prebuilt assignment
 * arrays, so we can prove the algorithm independently of Postgres.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { AssignmentService } from './assignment.service';

class FakeDb {
  constructor(private rows: any[]) {}
  async withTenantContext(_claims: any, fn: (c: any) => Promise<any>) {
    const client = {
      query: async (_sql: string, _params: unknown[]) => ({ rows: this.rows }),
    };
    return fn(client);
  }
}

describe('AssignmentService.resolveBillPayer', () => {
  const tenantId = '00000000-0000-0000-0000-000000000001';
  const aptId = '00000000-0000-0000-0000-000000000002';

  it('Scenario A: owner-occupant => current_bill_payer returns the owner', async () => {
    const svc = new AssignmentService(new FakeDb([
      { person_id: 'p-owner', role: 'owner', is_primary: true, is_occupant: true, is_bill_payer: true },
    ]) as any);
    const r = await svc.resolveBillPayer({ tenantId, apartmentId: aptId, rule: 'current_bill_payer' });
    expect(r.resolved_person_id).toBe('p-owner');
    expect(r.fallback_used).toBe(false);
  });

  it('Scenario B: renter is bill payer, owner is absentee', async () => {
    const svc = new AssignmentService(new FakeDb([
      { person_id: 'p-owner', role: 'owner', is_primary: true, is_occupant: false, is_bill_payer: false },
      { person_id: 'p-renter', role: 'renter', is_primary: true, is_occupant: true, is_bill_payer: true },
    ]) as any);
    const r = await svc.resolveBillPayer({ tenantId, apartmentId: aptId, rule: 'current_bill_payer' });
    expect(r.resolved_person_id).toBe('p-renter');
  });

  it('Scenario C: owner pays for renter — current_bill_payer returns owner', async () => {
    const svc = new AssignmentService(new FakeDb([
      { person_id: 'p-owner', role: 'owner', is_primary: true, is_occupant: false, is_bill_payer: true },
      { person_id: 'p-renter', role: 'renter', is_primary: true, is_occupant: true, is_bill_payer: false },
    ]) as any);
    const r = await svc.resolveBillPayer({ tenantId, apartmentId: aptId, rule: 'current_bill_payer' });
    expect(r.resolved_person_id).toBe('p-owner');
  });

  it('rule=owner returns the primary owner even if renter is bill_payer', async () => {
    const svc = new AssignmentService(new FakeDb([
      { person_id: 'p-owner', role: 'owner', is_primary: true, is_occupant: false, is_bill_payer: false },
      { person_id: 'p-renter', role: 'renter', is_primary: true, is_occupant: true, is_bill_payer: true },
    ]) as any);
    const r = await svc.resolveBillPayer({ tenantId, apartmentId: aptId, rule: 'owner' });
    expect(r.resolved_person_id).toBe('p-owner');
  });

  it('rule=specific_person_id honours the override', async () => {
    const svc = new AssignmentService(new FakeDb([]) as any);
    const r = await svc.resolveBillPayer({
      tenantId, apartmentId: aptId, rule: 'specific_person_id', specificPersonId: 'p-override',
    });
    expect(r.resolved_person_id).toBe('p-override');
  });

  it('Fallback: no bill_payer set, returns primary owner', async () => {
    const svc = new AssignmentService(new FakeDb([
      { person_id: 'p-owner', role: 'owner', is_primary: true, is_occupant: true, is_bill_payer: false },
    ]) as any);
    const r = await svc.resolveBillPayer({ tenantId, apartmentId: aptId, rule: 'current_bill_payer' });
    expect(r.resolved_person_id).toBe('p-owner');
    expect(r.fallback_used).toBe(true);
  });

  it('Vacancy: no assignments => resolved_person_id is null and reason explains', async () => {
    const svc = new AssignmentService(new FakeDb([]) as any);
    const r = await svc.resolveBillPayer({ tenantId, apartmentId: aptId, rule: 'current_bill_payer' });
    expect(r.resolved_person_id).toBeNull();
    expect(r.reason_no_payer).toBeTruthy();
  });
});
